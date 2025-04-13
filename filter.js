// static/filter_view.js

document.addEventListener('DOMContentLoaded', function() {
    // Find the single team filter dropdown on the page
    const teamFilter = document.getElementById('teamFilter');

    // Check if the filter dropdown exists (it might not if no fixtures were generated)
    if (teamFilter) {
        // Find all fixture tables on the page (they share the class .fixture-table)
        const fixtureTables = document.querySelectorAll('table.fixture-table');

        // Attach the event listener to the filter dropdown
        teamFilter.addEventListener('change', function() {
            const selectedTeam = this.value; // Get the selected team name ("all" or a specific team)

            // Loop through each fixture table found on the page
            fixtureTables.forEach(table => {
                const tableBody = table.tBodies[0]; // Get the table's body
                if (!tableBody) return; // Skip if table has no body

                // Find the corresponding "No results" message for this specific table
                // Assumes message ID is derived from table ID (e.g., table id="fixtureTable_League" -> msg id="noResultsMessage_League")
                // Decode any URL encoding applied by Flask's urlencode filter in the template
                const tableIdSuffix = decodeURIComponent(table.id.replace('fixtureTable_', ''));
                const noResultsMsg = document.getElementById(`noResultsMessage_${tableIdSuffix}`);

                // Get all the rows within this table's body that should be filterable
                const allRows = Array.from(tableBody.querySelectorAll('tr.fixture-row'));
                let visibleRowCount = 0; // Counter for visible rows in this specific table

                // Loop through each row in the current table
                allRows.forEach(row => {
                    const team1 = row.getAttribute('data-team1');
                    const team2 = row.getAttribute('data-team2');

                    // Determine if the row involves placeholders (like "Winner M1", "Loser(Q1)", "Rank 1 G...")
                    // Basic check: Placeholders often contain parentheses or specific prefixes
                    const isPlaceholderRow = (team1 && (team1.includes('(') || team1.toLowerCase().startsWith('rank'))) ||
                                             (team2 && (team2.includes('(') || team2.toLowerCase().startsWith('rank')));

                    // Determine if the row should be visible
                    // Logic: Show if 'all' is selected, OR if it's a placeholder row (usually want to see these regardless of team filter),
                    // OR if it's not a placeholder and one of the teams matches the filter.
                    const shouldBeVisible = (
                        selectedTeam === 'all' ||
                        isPlaceholderRow || // Always show placeholder rows? Adjust if needed.
                        (!isPlaceholderRow && (team1 === selectedTeam || team2 === selectedTeam))
                    );

                    // Add or remove the 'hidden-row' class based on visibility
                    // CSS in style.css handles the animation (opacity, max-height, transform)
                    if (shouldBeVisible) {
                        row.classList.remove('hidden-row');
                        // Ensure visibility is set for fade-in effect (important if transitioning from visibility: hidden)
                        row.style.visibility = 'visible';
                        visibleRowCount++; // Increment count for this table
                    } else {
                        row.classList.add('hidden-row');
                        // Note: CSS transition handles delaying visibility: hidden
                    }
                });

                // Show or hide the "No results" message for this specific table
                 if (noResultsMsg) {
                     // Show message only if a specific team is selected AND no rows are visible for that team in this table
                     if (visibleRowCount === 0 && selectedTeam !== 'all') {
                         noResultsMsg.classList.remove('hidden'); // Remove the utility class first
                         noResultsMsg.style.display = 'block'; // Ensure display is block before animating opacity
                         // Use setTimeout to trigger opacity transition after display change
                         // This allows the browser to register the display change before starting the opacity transition
                         setTimeout(() => { noResultsMsg.style.opacity = 1; }, 10); // Small delay
                     } else {
                         // Hide the message
                         noResultsMsg.style.opacity = 0; // Start fade out
                         // Add display:none and the .hidden class *after* the opacity transition completes
                          // Use setTimeout to approximate transition end
                          setTimeout(() => {
                               // Double-check opacity is still 0 before hiding completely,
                               // in case the filter changed again quickly.
                               if (noResultsMsg.style.opacity == 0) {
                                    noResultsMsg.classList.add('hidden');
                                    noResultsMsg.style.display = 'none'; // Fallback if class doesn't work
                               }
                          }, 300); // Should match the CSS transition duration for opacity (0.3s)
                     }
                 } else {
                    // Log if message element not found (for debugging)
                     if (visibleRowCount === 0 && selectedTeam !== 'all') {
                        console.warn(`Could not find 'noResultsMessage' element for table suffix: ${tableIdSuffix}`);
                     }
                 }

            }); // End looping through each table

        }); // End event listener for filter change

        // Optional: Trigger the filter once on page load if a value might be pre-selected
        // This ensures the initial view is correct if the form was re-submitted with a filter value
        // Use setTimeout to ensure tables are fully rendered maybe?
        // setTimeout(() => {
        //     if (teamFilter.value !== 'all') {
        //          teamFilter.dispatchEvent(new Event('change'));
        //     }
        // }, 100); // Small delay

    } // End if teamFilter exists

}); // End DOMContentLoaded