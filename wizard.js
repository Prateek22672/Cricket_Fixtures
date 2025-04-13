// static/wizard.js

// Use an Immediately Invoked Function Expression (IIFE) to avoid polluting global namespace
(function() {
    // --- State Variables ---
    let currentStep = 1; // Track the currently displayed step

    // --- DOM Element References ---
    // Get references once on load for efficiency
    const wizardForm = document.getElementById('wizardForm');
    const progressBar = document.getElementById('progressBar');
    const progressStep4 = document.getElementById('progressStep4'); // Progress bar marker for Step 4
    const includePlayoffsSelect = document.getElementById('include_playoffs');
    const step4Div = document.getElementById('step4'); // The actual Step 4 content div
    const teamsVenuesTextarea = document.getElementById('teams_venues');

    // --- Initialization ---
    document.addEventListener('DOMContentLoaded', function() {
        // Gracefully handle missing elements (though they should exist based on index.html)
        if (!wizardForm || !progressBar || !progressStep4 || !includePlayoffsSelect || !step4Div) {
            console.error("Wizard initialization failed: Could not find one or more essential wizard elements (form, progress bar, step 4 elements, playoff select). Check HTML IDs.");
            return; // Stop execution if basic structure is missing
        }

        showStep(currentStep); // Display the first step initially
        updateProgressBar();   // Set the initial state of the progress bar
        togglePlayoffStepVisibility(); // Check if playoff step should be visible/required initially

        // --- Event Listeners ---

        // Update progress bar and required fields when playoff choice changes
        includePlayoffsSelect.addEventListener('change', handlePlayoffChoiceChange);

        // Update Top 4 dropdown options when team/venue input changes (debounced)
        if (teamsVenuesTextarea) {
            // Update options after user pauses typing (500ms delay)
             teamsVenuesTextarea.addEventListener('input', debounce(updateTop4OptionsFromTextarea, 500));
             // Also update immediately on load in case the field is pre-populated (e.g., form error reload)
             updateTop4OptionsFromTextarea();
        } else {
             console.warn("Teams/Venues textarea not found. Dynamic Top 4 options will not update.");
        }

    }); // End DOMContentLoaded

    // --- Utility Functions ---

    // Debounce: Prevents a function from running too frequently
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func.apply(this, args); // Use apply to preserve context and arguments
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // --- Core Wizard Functions ---

    // Makes navigation functions globally accessible via `window` object
    // so they can be called by `onclick` attributes in the HTML.

    window.showStep = function(stepNum) {
        // Find all step divs within the form
        const steps = wizardForm.querySelectorAll('.wizard-step');
        const targetStepId = `step${stepNum}`;

        steps.forEach(step => {
            const isTargetStep = step.id === targetStepId;
            const isActive = step.classList.contains('active');

            if (isActive && !isTargetStep) {
                // If it's the currently active step but not the target, start exiting animation
               step.classList.add('exiting');
               // Remove 'active' and 'exiting' after the CSS animation completes
               setTimeout(() => {
                    step.classList.remove('active', 'exiting');
               }, 400); // Match --transition-speed in CSS (0.4s)
            } else if (isTargetStep && !isActive) {
                // If it's the target step and not already active, start entry animation
                step.classList.remove('exiting'); // Ensure no conflicting animation
                // Delay adding 'active' slightly allows exit animation to start cleanly
                setTimeout(() => {
                    step.classList.add('active');
                }, 10); // Small delay (10ms)
            } else if (!isTargetStep && !isActive) {
                 // Ensure inactive steps don't have animation classes
                 step.classList.remove('active', 'exiting');
            }
            // If it's the target step AND already active, do nothing.
        });

        currentStep = stepNum; // Update the global current step tracker
        updateProgressBar(); // Update the visual progress bar
    }

    window.nextStep = function(targetStep) {
        // Validate the *current* step before moving to the next one
        if (validateStep(currentStep)) {
            showStep(targetStep); // If valid, show the target step
        }
    }

    window.prevStep = function(targetStep) {
        // Typically, no validation is needed when going backward
        showStep(targetStep);
    }

    // Called by the 'Next' button on Step 3
    window.goToNextAppropriateStep = function(playoffStepNum) {
         const includePlayoffs = includePlayoffsSelect.value === 'yes';
         // Validate Step 3 first
         if (validateStep(currentStep)){
             if (includePlayoffs) {
                 // If playoffs are included, update the team options in Step 4 first
                 updateTop4OptionsFromTextarea();
                 nextStep(playoffStepNum); // Go to Step 4 (Playoffs) - nextStep includes validation
             } else {
                 // Skip Step 4 and submit the form
                 submitWizardForm();
             }
         }
    }

    function submitWizardForm() {
         // Optional: Disable submit button to prevent double clicks
         const submitButton = wizardForm.querySelector('button[type="submit"]'); // Usually in Step 4
         const generateButton = wizardForm.querySelector('.btn-wizard-generate'); // Or the specific generate button
         if (submitButton) submitButton.disabled = true;
         if (generateButton) generateButton.disabled = true; // Disable specific button too

         // Optional: Add loading indicator here
         console.log("Submitting form..."); // Log submission
         wizardForm.submit(); // Submit the form
    }

    // --- Progress Bar and Conditional Step Logic ---

    function updateProgressBar() {
        if (!progressBar) return; // Exit if progress bar element not found
        const progressSteps = progressBar.querySelectorAll('.progress-step');
        const includePlayoffs = includePlayoffsSelect.value === 'yes';
        // Determine total number of steps that should be visually represented
        const numVisibleSteps = includePlayoffs ? 4 : 3;

        progressSteps.forEach((step) => {
            const stepNum = parseInt(step.getAttribute('data-step'));
            // Mark step as 'active' in the progress bar if it's the current or a previous step
            step.classList.toggle('active', stepNum <= currentStep);

            // Specifically handle the visibility class for Step 4 marker
            if(step.id === 'progressStep4'){
                 step.classList.toggle('visible', includePlayoffs);
            }
        });

         // Calculate and update the active progress line's width
         let progressPercent = 0;
         if (numVisibleSteps > 1) {
              // Base the percentage on the current step relative to the number of *visible* steps
             let effectiveCurrentStep = currentStep;
             // Don't let progress go beyond step 3 if playoffs are disabled
             if (!includePlayoffs && currentStep > 3) {
                 effectiveCurrentStep = 3;
             }
             // Calculate percentage (e.g., step 1 of 3 -> 0%, step 2 of 3 -> 50%, step 3 of 3 -> 100%)
             progressPercent = ((effectiveCurrentStep - 1) / (numVisibleSteps - 1)) * 100;
         }
         // Apply the calculated width to the CSS variable used by the ::after pseudo-element
         progressBar.style.setProperty('--progress-width', `${Math.min(progressPercent, 100)}%`);
    }

    // Called when the "Include Playoffs?" dropdown changes
    function handlePlayoffChoiceChange() {
        togglePlayoffStepVisibility(); // Update required fields and step visibility
        updateProgressBar(); // Recalculate progress bar based on new total steps
        // If turning playoffs ON, update the options in the Top 4 dropdowns
        if (includePlayoffsSelect.value === 'yes') {
             updateTop4OptionsFromTextarea();
        }
    }

    // Updates the visibility and requirement status of Step 4 elements
    function togglePlayoffStepVisibility() {
        const includePlayoffs = includePlayoffsSelect.value === 'yes';

        // Toggle the visibility class on the progress bar marker for Step 4
        progressStep4.classList.toggle('visible', includePlayoffs);

        // Enable or disable the 'required' attribute on Step 4's select inputs
        const step4Selects = step4Div.querySelectorAll('select');
        step4Selects.forEach(select => {
            select.required = includePlayoffs; // Only required if playoffs are included
            // If hiding Step 4, remove any lingering validation error styles
            if (!includePlayoffs) {
                 select.style.border = ''; // Reset border style
            }
        });

        // If playoffs are turned off and the user is currently viewing Step 4,
        // automatically move them back to Step 3.
        if (!includePlayoffs && currentStep === 4) {
            showStep(3);
        }
    }

     // --- Dynamic Top 4 Dropdown Population ---
     function updateTop4OptionsFromTextarea() {
         // Don't run if the textarea doesn't exist
         if (!teamsVenuesTextarea) return;

         // Check if Step 4 should be visible based on the *current* playoff setting
         // We update the options regardless, but JS validation will only trigger if required/visible
         // const shouldBeVisible = includePlayoffsSelect.value === 'yes';

         const inputString = teamsVenuesTextarea.value;
         let teamsList = [];
         const lines = inputString.split('\n'); // Split into lines
         const seenTeams = new Set();

         // Parse lines to extract unique team names
         lines.forEach(line => {
             line = line.trim(); // Use JS trim()
             if (!line) return; // Skip empty lines
             // Split on first comma, map parts to trimmed strings
             // Ensure the parts are extracted correctly before accessing index 0
             const parts = line.split(',', 1); // Get the first part before comma
             if (parts.length >= 1) {
                 const teamName = parts[0].trim(); // Trim the extracted team name
                 if (teamName && !seenTeams.has(teamName)) { // Check if team name is not empty and unique
                     teamsList.push(teamName);
                     seenTeams.add(teamName);
                 }
             }
         });

         // Find all select elements within Step 4 (Top 1, Top 2, etc.)
         const selects = step4Div.querySelectorAll('select[name^="top"]'); // Selects where name starts with "top"
         selects.forEach(selectElement => {
             const currentVal = selectElement.value; // Store the currently selected value

             // Clear existing options, but keep the first one (the "-- Select --" placeholder)
             while (selectElement.options.length > 1) {
                 selectElement.remove(1); // Remove options starting from index 1
             }

             // Add the newly parsed team names as options
             teamsList.forEach(team => {
                 const option = new Option(team, team); // Option(text, value)
                 selectElement.add(option);
             });

             // Try to re-select the previously selected value if it's still in the list
             if (teamsList.includes(currentVal)) {
                 selectElement.value = currentVal;
             } else {
                 // If the previous value is no longer valid (team removed from textarea),
                 // reset to the placeholder (value="")
                 selectElement.value = "";
             }
         });
     }


    // --- Basic Step Validation Logic ---
    function validateStep(stepNum) {
        const stepElement = document.getElementById(`step${stepNum}`);
        if (!stepElement) {
             console.error(`Validation Error: Step element '#step${stepNum}' not found.`);
             return false; // Cannot validate, assume false to prevent proceeding
        }

        // Find all required inputs within the current step
        const inputs = stepElement.querySelectorAll('input[required], textarea[required], select[required]');
        let isValid = true;
        let firstInvalidElement = null; // To focus on the first error

        inputs.forEach(input => {
            // Reset previous error indication (remove red border)
            input.style.border = '';
            // Check if the input is actually visible on the page and is required
            // Includes check getClientRects().length > 0 for elements hidden with 'display: none'
            const isVisible = input.offsetWidth > 0 || input.offsetHeight > 0 || input.getClientRects().length > 0;

            // Validate only if the input is required and currently visible
            if (input.required && isVisible) {
                // Check if the input value (trimmed) is empty
                 if (!input.value || !input.value.trim()) {
                    input.style.border = '2px solid #dc3545'; // Apply Bootstrap's danger color border
                    isValid = false; // Mark step as invalid
                    // Keep track of the first invalid element to set focus later
                    if (!firstInvalidElement) firstInvalidElement = input;
                 }
            }
        });

         // Perform special validation for Step 4 (Playoff selections) ONLY if it's active and required
         if (stepNum === 4 && includePlayoffsSelect.value === 'yes') {
             const top1Select = document.getElementById('top1_team');
             const top2Select = document.getElementById('top2_team');
             const top3Select = document.getElementById('top3_team');
             const top4Select = document.getElementById('top4_team');

             // Check if elements exist before accessing value
             if(top1Select && top2Select && top3Select && top4Select) {
                 const selections = [top1Select.value, top2Select.value, top3Select.value, top4Select.value];

                 // First, ensure all are selected (required check handles most, but double-check)
                 if (selections.some(s => !s)) {
                     if (isValid) { // Only flag as primary error if no other empty required field was found
                        isValid = false;
                        if (!firstInvalidElement) firstInvalidElement = [top1Select, top2Select, top3Select, top4Select].find(s => !s.value);
                     }
                     // Mark empty selects specifically?
                     [top1Select, top2Select, top3Select, top4Select].forEach(sel => {
                         if (sel && !sel.value) sel.style.border = '2px solid #dc3545'; // Check sel exists
                     });

                 } else {
                     // If all are selected, check for uniqueness
                     if (new Set(selections).size !== 4) {
                         isValid = false;
                         // Indicate error on all 4 selects for uniqueness issue
                         [top1Select, top2Select, top3Select, top4Select].forEach(sel => {
                            if(sel) sel.style.border = '2px solid #dc3545'
                         });
                         if (!firstInvalidElement) firstInvalidElement = top1Select; // Focus the first one
                         // Use a more user-friendly notification than alert if possible
                         setTimeout(() => alert("Playoff Error: Please select a unique team for each Top 4 position."), 10);
                     }
                 }
             } else {
                 console.error("Validation Error: Could not find all Top 4 select elements.");
                 isValid = false; // Cannot validate if elements are missing
             }
         }


        // If validation failed for any reason in this step
        if (!isValid) {
            // Focus the first input element that failed validation
            if (firstInvalidElement) {
                firstInvalidElement.focus();
            }
            console.warn(`Validation failed for Step ${stepNum}`);
            // Consider adding a general error message near the buttons instead of an alert.
            // Example: document.getElementById('stepErrorMsg').textContent = 'Please fix errors above.';
        }

        return isValid; // Return true if all required visible inputs are valid, false otherwise
    }

})(); // End of IIFE