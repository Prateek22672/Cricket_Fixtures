# --- Required Imports ---
import math
import copy
import os
from flask import Flask, render_template, request, url_for, flash
from datetime import date, timedelta, datetime
import random
import itertools
import logging

# --- App Configuration ---
app = Flask(__name__)
# IMPORTANT: Use a strong, unique secret key, preferably from environment variables.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-secret-key-please-change')

# --- Constants ---
MIN_REST_DAYS = 2  # Minimum number of full days between matches for a team
WEEKDAY_MATCHES_LIMIT = 1 # Max matches per day (Mon-Fri) ACROSS ALL VENUES
WEEKEND_MATCHES_LIMIT = 2 # Max matches per day (Sat-Sun) ACROSS ALL VENUES
PLAYOFF_START_GAP_DAYS = 3 # Minimum days between last league match and first playoff match

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app.logger.setLevel(logging.INFO) # Ensure Flask logger uses this level

# --- Helper Functions ---

def parse_team_venue_pairs(input_string):
    """
    Parses newline-separated 'Team Name, Venue Name' strings.
    Returns: teams_list (list), venues_list (list), team_venue_map (dict)
    """
    teams_list = []
    venues_list = []
    team_venue_map = {}
    seen_teams = set()
    seen_venues = set()
    lines = input_string.strip().splitlines()
    line_num = 0
    for line in lines:
        line_num += 1
        line = line.strip()
        if not line: continue

        parts = [part.strip() for part in line.split(',', 1)]
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f"Invalid format on line {line_num}: '{line}'. Use 'Team Name, Venue Name'.")
        team_name, venue_name = parts

        if team_name in seen_teams:
             raise ValueError(f"Duplicate team name: '{team_name}' on line {line_num}.")

        teams_list.append(team_name)
        seen_teams.add(team_name)
        team_venue_map[team_name] = venue_name

        if venue_name not in seen_venues:
            venues_list.append(venue_name)
            seen_venues.add(venue_name)

    if not teams_list: raise ValueError("No valid team/venue pairs entered.")
    if len(teams_list) < 2: raise ValueError("At least two teams are required.")

    app.logger.info(f"Parsed {len(teams_list)} teams and {len(venues_list)} unique venues.")
    return teams_list, venues_list, team_venue_map

def date_range(start_date, end_date):
    """Generates date objects between start and end (inclusive)."""
    if start_date > end_date: return
    current_date = start_date
    while current_date <= end_date:
        yield current_date
        current_date += timedelta(days=1)

def get_available_slots(venues, start_date, end_date):
    """
    Generates potential slot dictionaries.
    Scheduling logic will enforce daily limits.
    """
    slots = []
    if not venues: return slots # Return empty list if no venues provided
    app.logger.info(f"Generating potential slots for {len(venues)} venues from {start_date} to {end_date}")
    for dt in date_range(start_date, end_date):
        # Create potential slots up to the max needed per day per venue
        max_slots_per_venue_per_day = WEEKEND_MATCHES_LIMIT
        for venue in venues:
            for i in range(max_slots_per_venue_per_day):
                 slots.append({
                     'date': dt,
                     'venue': venue,
                     'assigned': False,
                     'time_slot': i + 1
                 })
    slots.sort(key=lambda x: (x['date'], x['time_slot'], x['venue']))
    app.logger.info(f"Generated {len(slots)} total potential slots.")
    return slots

# --- Scheduling Logic ---
def schedule_matches(match_pairs, all_teams, available_slots, min_rest_days, team_venue_map, current_match_number=1, last_played_date=None, stage_name="League", round_num=None, venue_assignment_rule='home'):
    """
    Assigns match pairs to slots respecting constraints including MAX DAILY MATCHES.
    MODIFIES the 'assigned' status in the original available_slots list.
    """
    scheduled_fixtures_dicts = []
    if last_played_date is None:
        last_played_date = {team: None for team in all_teams}

    match_num_counter = current_match_number
    alternate_venue_counter = 0
    app.logger.info(f"Scheduling {len(match_pairs)} pairs for Stage: {stage_name}, Round: {round_num}. Daily Limits: {WEEKDAY_MATCHES_LIMIT}(Wkdy)/{WEEKEND_MATCHES_LIMIT}(Wknd). Rule: '{venue_assignment_rule}'.")
    shuffled_pairs = random.sample(match_pairs, len(match_pairs))
    required_rest_delta = timedelta(days=min_rest_days + 1)

    # --- Track matches scheduled per date during THIS run, considering pre-assigned slots ---
    matches_scheduled_on_date = {}
    for slot in available_slots:
        if slot['assigned']:
            matches_scheduled_on_date[slot['date']] = matches_scheduled_on_date.get(slot['date'], 0) + 1

    # --- Scheduling Loop ---
    for team1, team2 in shuffled_pairs:
        match_scheduled_this_pair = False
        preferred_venue = None
        # Determine Preferred Venue
        if venue_assignment_rule == 'home': preferred_venue = team_venue_map.get(team1)
        elif venue_assignment_rule == 'away': preferred_venue = team_venue_map.get(team2)
        elif venue_assignment_rule == 'alternate':
            preferred_venue = team_venue_map.get(team1) if alternate_venue_counter % 2 == 0 else team_venue_map.get(team2)
            alternate_venue_counter += 1
        # Fallback for random or if team not in map
        if not preferred_venue and venue_assignment_rule != 'random':
            all_unique_venues = list(set(team_venue_map.values()))
            if not all_unique_venues: raise ValueError(f"No venues found for fallback {team1} vs {team2}.")
            preferred_venue = random.choice(all_unique_venues)

        # Find earliest valid slot
        for slot in available_slots:
            # 1. Skip if already assigned in a previous call or earlier in this call
            if slot['assigned']: continue

            # 2. Daily Match Limit Check
            slot_date = slot['date']
            day_limit = WEEKEND_MATCHES_LIMIT if slot_date.weekday() >= 5 else WEEKDAY_MATCHES_LIMIT
            if matches_scheduled_on_date.get(slot_date, 0) >= day_limit:
                continue

            # 3. Venue constraint (only if not 'random')
            if venue_assignment_rule != 'random' and slot['venue'] != preferred_venue:
                continue

            # 4. Rest Days for actual teams
            t1_last = last_played_date.get(team1) if team1 in all_teams else None
            t2_last = last_played_date.get(team2) if team2 in all_teams else None
            rest_ok_t1 = t1_last is None or (slot_date - t1_last >= required_rest_delta)
            rest_ok_t2 = t2_last is None or (slot_date - t2_last >= required_rest_delta)
            if not (rest_ok_t1 and rest_ok_t2):
                continue

            # --- Slot Found - Schedule Match ---
            fixture_dict = { 'stage': stage_name, 'round': round_num, 'match_number': match_num_counter, 'match_type': None, 'date': slot_date, 'venue': slot['venue'], 'team1': team1, 'team2': team2, 'time_slot': slot['time_slot'] }
            scheduled_fixtures_dicts.append(fixture_dict)

            # Update last played dates
            if team1 in all_teams: last_played_date[team1] = slot_date
            if team2 in all_teams: last_played_date[team2] = slot_date

            # Mark original slot as assigned (!!! IMPORTANT !!!)
            slot['assigned'] = True

            # Increment daily match counter
            matches_scheduled_on_date[slot_date] = matches_scheduled_on_date.get(slot_date, 0) + 1

            match_scheduled_this_pair = True
            match_num_counter += 1
            break # Move to the next match pair

        if not match_scheduled_this_pair:
            remaining_slots = sum(1 for s in available_slots if not s['assigned'])
            raise ValueError(f"Could not schedule match {team1} vs {team2} (Stage: {stage_name}). Constraints too tight. Remaining potential slots: {remaining_slots}. Try extending dates.")

    # --- Final processing for this scheduling call ---
    scheduled_fixtures_dicts.sort(key=lambda x: (x['date'], x['time_slot']))
    last_match_date_in_stage = max((f['date'] for f in scheduled_fixtures_dicts), default=None)
    app.logger.info(f"Scheduled {len(scheduled_fixtures_dicts)} matches for Stage: {stage_name}.")
    return scheduled_fixtures_dicts, match_num_counter, last_played_date, last_match_date_in_stage

# --- Fixture Generation (Specific Types) ---

def generate_round_robin_fixtures(teams, venues, team_venue_map, start_date, end_date, min_rest_days):
    """ Generates Single Round Robin fixtures. """
    if len(teams) < 2: raise ValueError("Need >= 2 teams.")
    if not venues: raise ValueError("Need >= 1 venue.")
    base_pairings = list(itertools.combinations(teams, 2))
    available_slots = get_available_slots(venues, start_date, end_date)
    if not available_slots: raise ValueError("No available slots.")
    fixtures, _, _, last_date = schedule_matches(base_pairings, teams, available_slots, min_rest_days, team_venue_map, stage_name="League", venue_assignment_rule='home')
    return fixtures, last_date

def generate_double_round_robin_fixtures(teams, venues, team_venue_map, start_date, end_date, min_rest_days):
    """ Generates Double Round Robin fixtures. """
    if len(teams) < 2: raise ValueError("Need >= 2 teams.")
    if not venues: raise ValueError("Need >= 1 venue.")
    leg1_pairings = list(itertools.combinations(teams, 2))
    leg2_pairings = [(p[1], p[0]) for p in leg1_pairings]
    available_slots = get_available_slots(venues, start_date, end_date)
    if not available_slots: raise ValueError("No available slots.")
    leg1_fixtures, match_counter, last_played, last_date_leg1 = schedule_matches(leg1_pairings, teams, available_slots, min_rest_days, team_venue_map, stage_name="League (Leg 1)", venue_assignment_rule='home')
    leg2_fixtures, _, _, last_date_leg2 = schedule_matches(leg2_pairings, teams, available_slots, min_rest_days, team_venue_map, match_counter, last_played, stage_name="League (Leg 2)", venue_assignment_rule='home')
    all_fixtures = leg1_fixtures + leg2_fixtures
    all_fixtures.sort(key=lambda x: (x['date'], x['time_slot']))
    for i, fixture in enumerate(all_fixtures): fixture['match_number'] = i + 1
    last_date = max(last_date_leg1, last_date_leg2) if last_date_leg1 and last_date_leg2 else (last_date_leg1 or last_date_leg2)
    return all_fixtures, last_date

def generate_single_elimination_fixtures(teams, venues, team_venue_map, start_date, end_date, min_rest_days):
    """ Generates Single Elimination fixtures. """
    num_teams = len(teams)
    if num_teams < 2: raise ValueError("Need >= 2 teams.")
    if not venues: raise ValueError("Need >= 1 venue.")
    all_fixtures = []; match_counter = 1; last_played = {team: None for team in teams}
    next_power_of_2 = 1 << (num_teams - 1).bit_length(); num_byes = next_power_of_2 - num_teams
    shuffled_teams = random.sample(teams, num_teams); round1_participants = shuffled_teams[num_byes:]
    byes_list = shuffled_teams[:num_byes]; current_participants = byes_list[:]; current_round = 1
    earliest_next_round_start = start_date
    available_slots = get_available_slots(venues, start_date, end_date) # Get all slots once
    if not available_slots: raise ValueError(f"No slots between {start_date} and {end_date}")

    # Round 1
    round1_pairs = [(round1_participants[i], round1_participants[i+1]) for i in range(0, len(round1_participants), 2)]
    if round1_pairs:
        r1_fixtures, match_counter, last_played, last_date_r1 = schedule_matches(round1_pairs, teams, available_slots, min_rest_days, team_venue_map, match_counter, last_played, stage_name="Knockout", round_num=current_round, venue_assignment_rule='random')
        all_fixtures.extend(r1_fixtures)
        current_participants.extend([f"Winner R{current_round}M{f['match_number']}" for f in r1_fixtures]) # Use overall match number
        if last_date_r1: earliest_next_round_start = last_date_r1 + timedelta(days=min_rest_days + 1)

    # Subsequent Rounds
    while len(current_participants) > 1:
        current_round += 1;
        if len(current_participants) % 2 != 0: raise ValueError("Internal Error: Odd participants in SE round.")
        next_round_pairs = []; random.shuffle(current_participants)
        for i in range(0, len(current_participants), 2): next_round_pairs.append((current_participants[i], current_participants[i+1]))
        # Pass the main available_slots list; schedule_matches handles date progression
        round_fixtures, match_counter, last_played, last_date_round = schedule_matches(next_round_pairs, teams, available_slots, min_rest_days, team_venue_map, match_counter, last_played, stage_name="Knockout", round_num=current_round, venue_assignment_rule='random')
        all_fixtures.extend(round_fixtures)
        current_participants = [f"Winner R{current_round}M{f['match_number']}" for f in round_fixtures] # Use overall match number
        if last_date_round: earliest_next_round_start = last_date_round + timedelta(days=min_rest_days + 1)

    all_fixtures.sort(key=lambda x: (x['date'], x['time_slot']))
    # Renumber all matches sequentially AFTER all generation is complete
    # This renumbering happens in the main route now.
    # for i, fixture in enumerate(all_fixtures): fixture['match_number'] = i + 1
    final_match_date = max((f['date'] for f in all_fixtures), default=None)
    return all_fixtures, final_match_date

def generate_double_elimination_fixtures(teams, venues, team_venue_map, start_date, end_date, min_rest_days):
    """ Generates Double Elimination fixtures (Simplified Placeholder). """
    if len(teams) < 4: raise ValueError("Double Elimination typically requires >= 4 teams.")
    if not venues: raise ValueError("Need >= 1 venue.")
    flash("Warning: Double Elimination generation is currently simplified (uses Single Elimination structure).", "warning")
    app.logger.warning("Double Elimination called, using Single Elimination logic.")
    return generate_single_elimination_fixtures(teams, venues, team_venue_map, start_date, end_date, min_rest_days)

def generate_group_stage_knockout_fixtures(teams, venues, team_venue_map, start_date, end_date, min_rest_days, teams_per_group=4, groups_to_advance=2):
    """ Generates Group Stage (RR) + Knockout (SE) fixtures. """
    num_teams = len(teams);
    if num_teams < 4: raise ValueError("Need >= 4 teams.")
    if not venues: raise ValueError("Need >= 1 venue.")
    if teams_per_group <= 1: raise ValueError("Teams per group must be > 1.")
    if num_teams % teams_per_group != 0: raise ValueError(f"Team count ({num_teams}) not divisible by {teams_per_group}.")
    num_groups = num_teams // teams_per_group
    if groups_to_advance * num_groups < 2 and groups_to_advance > 0: flash("Warning: Not enough teams advancing for knockout.", "warning")
    shuffled_teams = random.sample(teams, num_teams)
    groups = [shuffled_teams[i*teams_per_group:(i+1)*teams_per_group] for i in range(num_groups)]
    all_fixtures = []; match_counter = 1; last_played = {team: None for team in teams}; last_group_match_date = None
    total_days = max(1, (end_date - start_date).days); group_stage_days = max(7, total_days * 2 // 3)
    ko_rounds = 0; min_ko_days = 0
    if groups_to_advance * num_groups >=2: ko_rounds = math.ceil(math.log2(groups_to_advance * num_groups))
    min_ko_days = ko_rounds * (min_rest_days + 1) + 1 # Min days per KO round + buffer
    group_stage_end_date = min(start_date + timedelta(days=group_stage_days), end_date - timedelta(days=min_ko_days))
    group_stage_end_date = max(group_stage_end_date, start_date)

    available_slots = get_available_slots(venues, start_date, end_date) # Get all slots once
    if not available_slots: raise ValueError(f"No slots available between {start_date} and {end_date}.")

    # --- Group Stage ---
    app.logger.info(f"Generating Group Stage ({num_groups} groups) until potential end {group_stage_end_date}")
    original_assigned_count = sum(1 for s in available_slots if s['assigned'])
    for i, group in enumerate(groups):
        group_name = chr(65 + i); group_pairings = list(itertools.combinations(group, 2))
        group_fixtures, mc_after_group, last_played, last_date_this_group = schedule_matches(
            group_pairings, teams, available_slots, min_rest_days, team_venue_map,
            match_counter, last_played, f"Group {group_name}", venue_assignment_rule='home'
        )
        all_fixtures.extend(group_fixtures); match_counter = mc_after_group
        if last_date_this_group: last_group_match_date = max(last_group_match_date, last_date_this_group) if last_group_match_date else last_date_this_group
    group_slots_used_count = sum(1 for s in available_slots if s['assigned']) - original_assigned_count
    app.logger.info(f"Group stage used {group_slots_used_count} slots, ending on {last_group_match_date}")

    # --- Knockout Stage ---
    app.logger.info(f"Generating Knockout Stage (Advancing {groups_to_advance})")
    num_knockout_teams = num_groups * groups_to_advance
    last_overall_date = last_group_match_date # Default if no KO
    if num_knockout_teams >= 2:
        knockout_qualifiers = [f"Rank {j+1} G{chr(65+i)}" for i in range(num_groups) for j in range(groups_to_advance)]
        knockout_start_date = last_group_match_date + timedelta(days=min_rest_days + 1) if last_group_match_date else start_date + timedelta(days=1)
        knockout_start_date = max(knockout_start_date, start_date + timedelta(days=1))
        if knockout_start_date > end_date:
            flash("Warning: No time left for knockout stage.", "warning");
        else:
            app.logger.info(f"Knockout stage starting from {knockout_start_date}")
            # Create dummy map for placeholders if needed by internal calls (though SE uses random venues)
            placeholder_map = {q: random.choice(venues) for q in knockout_qualifiers if venues} if knockout_qualifiers else {}
            # Pass the MAIN available_slots list; SE will use remaining slots >= knockout_start_date
            knockout_fixtures, last_ko_date = generate_single_elimination_fixtures(
                knockout_qualifiers, venues, placeholder_map,
                knockout_start_date, end_date, min_rest_days
            )
            # Adjust stage name and potentially match numbers (SE returns renumbered list)
            base_ko_match_num = match_counter -1 # Matches before KO
            for fix in knockout_fixtures:
                fix['stage'] = "Knockout"
                # We will renumber globally later
                # fix['match_number'] += base_ko_match_num
            all_fixtures.extend(knockout_fixtures); last_overall_date = last_ko_date or last_group_match_date
    else: app.logger.info("Not enough teams for knockout.")

    # Final sort happens before renumbering in main route
    # all_fixtures.sort(key=lambda x: (x['date'], x['time_slot']))
    # for i, fixture in enumerate(all_fixtures): fixture['match_number'] = i + 1
    return all_fixtures, last_overall_date


# --- IPL Style Playoffs (Top 4 - Updated for Sunday Final & Gap) ---
def generate_playoffs_top4(actual_top_4_teams, last_league_date, venues, team_venue_map, min_rest_days):
    """ Generates IPL playoffs ensuring start gap and attempting Sunday Final. """
    if len(actual_top_4_teams) != 4: return [], last_league_date
    app.logger.info(f"Generating Top 4 Playoffs for: {actual_top_4_teams}")
    t1, t2, t3, t4 = actual_top_4_teams
    playoff_structure = [ {'match_id': 'Q1', 'type': 'Qualifier 1', 't1': t1, 't2': t2}, {'match_id': 'Elim', 'type': 'Eliminator', 't1': t3, 't2': t4}, {'match_id': 'Q2', 'type': 'Qualifier 2', 't1': f"Loser(Q1)", 't2': f"Winner(Elim.)"}, {'match_id': 'Final', 'type': 'Final', 't1': f"Winner(Q1)", 't2': f"Winner(Q2)"}, ]
    teams_involved_map = {'Q1': [t1, t2], 'Elim': [t3, t4], 'Q2': [t1, t2, t3, t4], 'Final': [t1, t2, t3, t4]}
    playoff_min_start_date = last_league_date + timedelta(days=PLAYOFF_START_GAP_DAYS) if last_league_date else date.today() + timedelta(days=PLAYOFF_START_GAP_DAYS)
    app.logger.info(f"Playoffs must start on or after: {playoff_min_start_date}")
    playoff_end_date_estimate = playoff_min_start_date + timedelta(days=21) # Window
    available_playoff_slots_orig = get_available_slots(venues, playoff_min_start_date, playoff_end_date_estimate)
    if not available_playoff_slots_orig: raise ValueError(f"No slots found for playoffs starting from {playoff_min_start_date}.")

    playoff_fixtures_dicts = []; playoff_last_played = {team: last_league_date for team in actual_top_4_teams}
    match_dates = {}; required_rest_delta = timedelta(days=min_rest_days + 1)
    last_scheduled_date = None # Track actual last date scheduled *within playoffs*
    available_playoff_slots = [s.copy() for s in available_playoff_slots_orig] # Work with copy
    playoff_matches_on_date = {} # Track daily counts specific to playoffs

    # Schedule Q1, Elim, Q2
    for match_info in playoff_structure:
        if match_info['match_id'] == 'Final': continue
        match_id = match_info['match_id']; match_scheduled = False
        min_start_date_rest = last_scheduled_date + required_rest_delta if last_scheduled_date else playoff_min_start_date
        min_start_date = max(min_start_date_rest, playoff_min_start_date)
        involved_teams = teams_involved_map[match_id]
        app.logger.debug(f"Scheduling {match_id}. Min start: {min_start_date}")
        for slot in available_playoff_slots:
            slot_date = slot['date']
            if slot['assigned'] or slot_date < min_start_date: continue
            playoff_day_limit = WEEKEND_MATCHES_LIMIT if slot_date.weekday() >= 5 else WEEKDAY_MATCHES_LIMIT # Use daily limits
            if playoff_matches_on_date.get(slot_date, 0) >= playoff_day_limit: continue
            rest_ok = all(playoff_last_played.get(team) is None or (slot_date - playoff_last_played.get(team) >= required_rest_delta) for team in involved_teams)
            if rest_ok:
                fixture_dict = { 'match_number': 0, 'match_type': match_info['type'], 'stage': 'Playoffs', 'round': None, 'date': slot_date, 'venue': slot['venue'], 'team1': match_info['t1'], 'team2': match_info['t2'], 'time_slot': slot['time_slot'] }
                playoff_fixtures_dicts.append(fixture_dict); slot['assigned'] = True; match_scheduled = True
                match_dates[match_id] = slot_date; last_scheduled_date = slot_date # Update last PLAYOFF date
                playoff_matches_on_date[slot_date] = playoff_matches_on_date.get(slot_date, 0) + 1
                for team in involved_teams: playoff_last_played[team] = slot_date
                app.logger.debug(f"Scheduled {match_id} on {slot_date}. Day count: {playoff_matches_on_date[slot_date]}/{playoff_day_limit}")
                break
        if not match_scheduled: raise ValueError(f"Could not schedule playoff match: {match_info['type']}.")

    # Schedule Final on nearest Sunday
    final_match_info = next(m for m in playoff_structure if m['match_id'] == 'Final')
    q2_date = match_dates.get('Q2')
    # --- FIXED SYNTAX ERROR HERE ---
    if not q2_date:
        raise ValueError("Internal Error: Q2 date not found for Final scheduling.")
    # --- END FIX ---
    earliest_final_start_date = q2_date + required_rest_delta
    target_sunday = earliest_final_start_date
    while target_sunday.weekday() != 6: target_sunday += timedelta(days=1)
    app.logger.info(f"Targeting Sunday {target_sunday} for the Final.")
    final_scheduled = False; involved_final_teams = teams_involved_map['Final']
    for slot in available_playoff_slots: # Check remaining playoff slots
        slot_date = slot['date']
        if slot['assigned'] or slot_date != target_sunday: continue
        playoff_day_limit = WEEKEND_MATCHES_LIMIT # Sunday limit
        if playoff_matches_on_date.get(slot_date, 0) >= playoff_day_limit: continue
        final_rest_ok = all(playoff_last_played.get(team) is None or (slot_date - playoff_last_played.get(team) >= required_rest_delta) for team in involved_final_teams)
        if final_rest_ok:
            fixture_dict = { 'match_number': 0, 'match_type': final_match_info['type'], 'stage': 'Playoffs', 'round': None, 'date': slot_date, 'venue': slot['venue'], 'team1': final_match_info['t1'], 'team2': final_match_info['t2'], 'time_slot': slot['time_slot'] }
            playoff_fixtures_dicts.append(fixture_dict); slot['assigned'] = True; final_scheduled = True
            last_scheduled_date = slot_date; playoff_matches_on_date[slot_date] = playoff_matches_on_date.get(slot_date, 0) + 1
            app.logger.info(f"Scheduled Final on Sunday {slot_date}")
            break
    if not final_scheduled: # Fallback: Find next available slot after target sunday
        app.logger.warning(f"Could not schedule Final on target Sunday {target_sunday}. Searching...")
        next_possible_date = target_sunday + timedelta(days=1)
        for slot in available_playoff_slots:
            slot_date = slot['date']
            if slot['assigned'] or slot_date < next_possible_date: continue
            playoff_day_limit = WEEKEND_MATCHES_LIMIT if slot_date.weekday() >= 5 else WEEKDAY_MATCHES_LIMIT
            if playoff_matches_on_date.get(slot_date, 0) >= playoff_day_limit: continue
            final_rest_ok = all(playoff_last_played.get(team) is None or (slot_date - playoff_last_played.get(team) >= required_rest_delta) for team in involved_final_teams)
            if final_rest_ok:
                 fixture_dict = { 'match_number': 0, 'match_type': final_match_info['type'], 'stage': 'Playoffs', 'round': None, 'date': slot_date, 'venue': slot['venue'], 'team1': final_match_info['t1'], 'team2': final_match_info['t2'], 'time_slot': slot['time_slot'] }
                 playoff_fixtures_dicts.append(fixture_dict); slot['assigned'] = True; final_scheduled = True
                 last_scheduled_date = slot_date; playoff_matches_on_date[slot_date] = playoff_matches_on_date.get(slot_date, 0) + 1
                 flash(f"Warning: Could not schedule Final on target Sunday ({target_sunday}). Scheduled on next available day: {slot_date}.", "warning")
                 app.logger.info(f"Scheduled Final on fallback day {slot_date}")
                 break
        if not final_scheduled: raise ValueError(f"Could not schedule Final. No suitable slots after {earliest_final_start_date}.")

    playoff_fixtures_dicts.sort(key=lambda x: (x['date'], x['time_slot']))
    for i, fixture in enumerate(playoff_fixtures_dicts): fixture['match_number'] = i + 1 # Renumber within playoffs
    return playoff_fixtures_dicts, last_scheduled_date

# --- Post-Scheduling Check ---
def check_schedule_gaps(fixtures, start_date, end_date):
    """ Checks if matches were scheduled on expected days based on overall daily limits. """
    if not fixtures or not start_date or not end_date: return
    scheduled_dates_count = {}
    for f in fixtures: scheduled_dates_count[f['date']] = scheduled_dates_count.get(f['date'], 0) + 1
    missed_days_count = 0; total_days = 0; underutilized_days = 0
    current_date = start_date
    while current_date <= end_date:
        total_days += 1
        is_weekend = current_date.weekday() >= 5
        expected_matches_today = WEEKEND_MATCHES_LIMIT if is_weekend else WEEKDAY_MATCHES_LIMIT
        matches_on_day = scheduled_dates_count.get(current_date, 0)
        if matches_on_day == 0 and expected_matches_today > 0:
             missed_days_count += 1; app.logger.warning(f"Schedule Gap: No matches on {current_date} ({current_date.strftime('%a')}).")
        elif matches_on_day > 0 and matches_on_day < expected_matches_today:
             underutilized_days += 1; app.logger.warning(f"Schedule Under-utilization: {matches_on_day}/{expected_matches_today} matches on {current_date} ({current_date.strftime('%a')}).")
        current_date += timedelta(days=1)
    if missed_days_count > 0: flash(f"Warning: Scheduling resulted in {missed_days_count}/{total_days} days potentially having no matches scheduled due to constraints.", "warning")
    elif underutilized_days > 0: flash(f"Note: {underutilized_days}/{total_days} days had fewer matches than the maximum allowed due to constraints.", "info")


# --- Flask Main Route ---
@app.route('/', methods=['GET', 'POST'])
def index():
    """ Handles displaying the form and processing fixture generation requests. """
    error_message = None; fixtures_by_stage = {}; teams_list_for_template = []
    if request.method == 'POST':
        app.logger.info("Received POST request.")
        try:
            # Get & Validate Form Data
            team_venue_raw = request.form.get('teams_venues'); start_date_str = request.form.get('start_date')
            end_date_str = request.form.get('end_date'); tournament_type = request.form.get('tournament_type')
            include_playoffs_str = request.form.get('include_playoffs'); tournament_name = request.form.get('tournament_name') or "Unnamed Tournament"
            if not all([team_venue_raw, start_date_str, end_date_str, tournament_type]): raise ValueError("Missing required fields.")
            teams_list, venues_list, team_venue_map = parse_team_venue_pairs(team_venue_raw)
            teams_list_for_template = teams_list
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date(); end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            include_playoffs = include_playoffs_str.lower() == 'yes' if include_playoffs_str else False
            if start_date > end_date: raise ValueError("End Date cannot be before Start Date.")

            # Validate Top 4 Teams if needed
            actual_top_4_teams = []
            if include_playoffs and tournament_type in ['round_robin', 'double_round_robin']:
                if len(teams_list) < 4: raise ValueError("Need >= 4 teams for Top 4 Playoffs.")
                top1 = request.form.get('top1_team'); top2 = request.form.get('top2_team'); top3 = request.form.get('top3_team'); top4 = request.form.get('top4_team')
                actual_top_4_teams = [top1, top2, top3, top4]
                if not all(actual_top_4_teams): raise ValueError("Must select all Top 4 teams if playoffs enabled.")
                if len(set(actual_top_4_teams)) != 4: raise ValueError("Top 4 selections must be unique.")
                for team in actual_top_4_teams:
                    if team not in teams_list: raise ValueError(f"Top 4 team '{team}' not in main list.")

            # --- Generate Fixtures ---
            app.logger.info(f"Starting generation: Type='{tournament_type}', Playoffs={include_playoffs}")
            fixture_dicts = []; last_main_stage_date = None;

            # Call appropriate generation function
            if tournament_type == 'round_robin':
                fixture_dicts, last_main_stage_date = generate_round_robin_fixtures(teams_list, venues_list, team_venue_map, start_date, end_date, MIN_REST_DAYS)
                if include_playoffs:
                     playoff_fixtures, _ = generate_playoffs_top4(actual_top_4_teams, last_main_stage_date, venues_list, team_venue_map, MIN_REST_DAYS)
                     fixture_dicts.extend(playoff_fixtures)
            elif tournament_type == 'double_round_robin':
                fixture_dicts, last_main_stage_date = generate_double_round_robin_fixtures(teams_list, venues_list, team_venue_map, start_date, end_date, MIN_REST_DAYS)
                if include_playoffs:
                     playoff_fixtures, _ = generate_playoffs_top4(actual_top_4_teams, last_main_stage_date, venues_list, team_venue_map, MIN_REST_DAYS)
                     fixture_dicts.extend(playoff_fixtures)
            elif tournament_type == 'single_elimination':
                 fixture_dicts, last_main_stage_date = generate_single_elimination_fixtures(teams_list, venues_list, team_venue_map, start_date, end_date, MIN_REST_DAYS)
            elif tournament_type == 'double_elimination':
                 fixture_dicts, last_main_stage_date = generate_double_elimination_fixtures(teams_list, venues_list, team_venue_map, start_date, end_date, MIN_REST_DAYS)
            elif tournament_type == 'group_knockout':
                 fixture_dicts, last_main_stage_date = generate_group_stage_knockout_fixtures(teams_list, venues_list, team_venue_map, start_date, end_date, MIN_REST_DAYS)
            else: raise ValueError(f"Invalid tournament type: {tournament_type}")

            # --- Post-Generation Processing ---
            if not fixture_dicts:
                 flash("No fixtures could be generated. Check constraints or date range.", "warning")
            else:
                 flash(f"Fixtures generated successfully for '{tournament_name}'!", "success")
                 app.logger.info(f"Generated {len(fixture_dicts)} fixtures.")
                 actual_end_date = max((f['date'] for f in fixture_dicts), default=end_date)
                 check_schedule_gaps(fixture_dicts, start_date, actual_end_date) # Check gaps

                 # Group fixtures by stage & Renumber Overall
                 fixture_dicts.sort(key=lambda x: (x['date'], x['time_slot']))
                 for i, f_dict in enumerate(fixture_dicts):
                      f_dict['match_number'] = i + 1 # Assign overall sequential match number
                      stage = f_dict.get('stage', 'Fixtures')
                      if stage not in fixtures_by_stage: fixtures_by_stage[stage] = []
                      if 'date' in f_dict and not isinstance(f_dict['date'], date): # Date conversion check
                         try: f_dict['date'] = datetime.strptime(f_dict['date'], '%Y-%m-%d').date()
                         except: f_dict['date'] = None; app.logger.error("Date conversion failed.")
                      fixtures_by_stage[stage].append(f_dict)

        except ValueError as e: # Handle known errors
            error_message = str(e); flash(f"Error: {error_message}", "danger")
            app.logger.error(f"Validation/Generation Error: {e}")
            if not teams_list_for_template and request.form.get('teams_venues'):
                 try: teams_list_for_template, _, _ = parse_team_venue_pairs(request.form.get('teams_venues'))
                 except ValueError: teams_list_for_template = []
        except Exception as e: # Handle unexpected errors
            error_message = "An unexpected server error occurred."; flash(error_message, "danger")
            app.logger.exception("Unexpected error during fixture generation:")
            if not teams_list_for_template and request.form.get('teams_venues'):
                 try: teams_list_for_template, _, _ = parse_team_venue_pairs(request.form.get('teams_venues'))
                 except ValueError: teams_list_for_template = []

    # --- Render Template (GET or POST) ---
    return render_template( 'index.html', fixtures_by_stage=fixtures_by_stage, error=error_message, request=request, teams_list=teams_list_for_template)

# --- Main Execution ---
if __name__ == '__main__':
    app.logger.setLevel(logging.DEBUG) # Use DEBUG for more detail during development
    # Set host='0.0.0.0' for accessibility within VM/docker or network
    # Set debug=True for auto-reload and interactive debugger
    app.run(debug=True, host='0.0.0.0', port=5000)