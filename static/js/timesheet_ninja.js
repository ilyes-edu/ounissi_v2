/**
 * Timesheet Ninja Integration
 * Handles single and bulk validation for the attendance dashboard.
 * Requires global variables NINJA_API_URL and CSRF_TOKEN to be defined in the template.
 */

// 1. Helper to extract data from a specific table row
function getRowData(rowId) {
    const row = document.getElementById(`row-${rowId}`);
    if (!row) {
        console.error(`Row with ID row-${rowId} not found.`);
        return null;
    }

    return {
        id: parseInt(rowId),
        start_time: row.querySelector('.start_time').value || null,
        end_time: row.querySelector('.end_time').value || null,
        start_time_2: row.querySelector('.start_time_2').value || null,
        end_time_2: row.querySelector('.end_time_2').value || null,
        start_time_3: row.querySelector('.start_time_3').value || null,
        end_time_3: row.querySelector('.end_time_3').value || null,
    };
}

// 2. Core function to send data to the Ninja API
async function postToNinja(payload, rowElements) {
    console.log("Sending payload to Ninja:", payload);

    try {
        const response = await fetch(NINJA_API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": CSRF_TOKEN
            },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (response.ok) {
            console.log("Ninja Success:", result.message);

            // Visual feedback for successful rows
            rowElements.forEach(row => {
                row.style.transition = "background-color 0.8s";
                row.style.backgroundColor = "#e8f5e9"; // Soft Success Green
                row.classList.remove('w3-pale-red'); // Remove warning color if present

                const btn = row.querySelector('button[id^="btn-"]');
                if (btn) btn.innerHTML = "✅";
            });
            return true;
        } else {
            console.error("Ninja Validation Error:", result.detail);
            alert("Validation Error: Check console for details.");
            return false;
        }
    } catch (error) {
        console.error("Network or API Error:", error);
        alert("Server communication failed. Is the Django server running?");
        return false;
    }
}

// 3. Single Line Validation
async function saveSingleLine(id) {
    console.log(`Saving single line: ${id}`);
    const row = document.getElementById(`row-${id}`);
    const btn = document.getElementById(`btn-${id}`);

    const originalBtnIcon = btn.innerHTML;
    btn.innerHTML = "⏳";

    const data = getRowData(id);
    if (!data) return;

    const success = await postToNinja([data], [row]);
    if (!success) btn.innerHTML = originalBtnIcon;
}

// 4. Bulk Validation for the entire visible list
async function executeBulkValidation() {
    const bulkBtn = document.getElementById('bulk-btn');
    const tableRows = document.querySelectorAll('tr[id^="row-"]');
    const warningRows = document.querySelectorAll('tr.w3-pale-red'); // Count red rows

    if (tableRows.length === 0) return;

    // Smart Warning Message
    let confirmMessage = `Confirmer la validation de ${tableRows.length} lignes ?`;

    if (warningRows.length > 0) {
        confirmMessage = `⚠️ ATTENTION: Il y a ${warningRows.length} lignes avec des anomalies (en rouge). \n\nEtes-vous sûr de vouloir tout valider sans corriger ?`;
    }

    if (!confirm(confirmMessage)) return;

    const payload = [];
    const rowsArray = [];

    const originalBtnText = bulkBtn.innerHTML;
    bulkBtn.innerHTML = "⏳ En cours...";
    bulkBtn.disabled = true;

    tableRows.forEach(row => {
        const id = row.id.split('-')[1];
        const data = getRowData(id);
        if (data) {
            payload.push(data);
            rowsArray.push(row);
        }
    });

    const success = await postToNinja(payload, rowsArray);

    if (success) {
        bulkBtn.innerHTML = "✅ Liste Validée";
        bulkBtn.className = "w3-button w3-light-grey w3-round-large"; // Change style to show it's done
    } else {
        bulkBtn.innerHTML = originalBtnText;
        bulkBtn.disabled = false;
    }
}