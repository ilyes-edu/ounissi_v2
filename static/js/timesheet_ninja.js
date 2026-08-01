/**
 * Timesheet Ninja Integration
 * Handles single and bulk validation for the attendance dashboard.
 * Requires global variables NINJA_API_URL and CSRF_TOKEN to be defined in the template.
 */

// 1. Helper to extract data from both new and existing table rows
function extractRowData(row) {
    if (!row) return null;

    const leaveTypeEl = row.querySelector('.leave_type');
    const rowIdAttr = row.id; // e.g., "row-123" or "row-new-12-2026-07-25"

    let id = null;
    let employeeId = null;
    let dateStr = null;

    // Detect if this is an unsaved row
    if (rowIdAttr.startsWith("row-new-")) {
        const parts = rowIdAttr.split('-');
        employeeId = parseInt(parts[2]);
        dateStr = `${parts[3]}-${parts[4]}-${parts[5]}`; // Reassemble YYYY-MM-DD
    } else {
        id = parseInt(rowIdAttr.split('-')[1]);
    }

    return {
        id: id,
        employee_id: employeeId,
        date: dateStr,
        start_time: row.querySelector('.start_time').value || null,
        end_time: row.querySelector('.end_time').value || null,
        start_time_2: row.querySelector('.start_time_2').value || null,
        end_time_2: row.querySelector('.end_time_2').value || null,
        start_time_3: row.querySelector('.start_time_3').value || null,
        end_time_3: row.querySelector('.end_time_3').value || null,
        leave_type: leaveTypeEl ? leaveTypeEl.value : 'NONE',
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

                // Check for standard or new save buttons inside the row
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

// 3. Existing Row Single Line Validation
async function saveSingleLine(id) {
    console.log(`Saving single line: ${id}`);
    const row = document.getElementById(`row-${id}`);
    const btn = document.getElementById(`btn-${id}`);
    if (!row || !btn) return;

    const originalBtnIcon = btn.innerHTML;
    btn.innerHTML = "⏳";

    const data = extractRowData(row);
    if (!data) return;

    const success = await postToNinja([data], [row]);
    if (!success) btn.innerHTML = originalBtnIcon;
}

// 3.1 New Row Single Line Validation
async function saveNewSingleLine(btnElement, employeeId, dateStr) {
    console.log(`Creating single line for Employee: ${employeeId}, Date: ${dateStr}`);
    const row = btnElement.closest('tr');
    if (!row) return;

    const originalBtnIcon = btnElement.innerHTML;
    btnElement.innerHTML = "⏳";

    const data = extractRowData(row);
    if (!data) return;

    const success = await postToNinja([data], [row]);
    if (!success) btnElement.innerHTML = originalBtnIcon;
}

// 4. Bulk Validation for the entire visible list (Supports both new and existing rows)
async function executeBulkValidation() {
    const bulkBtn = document.getElementById('bulk-btn');
    const tableRows = document.querySelectorAll('tr[id^="row-"]');
    const warningRows = document.querySelectorAll('tr.w3-pale-red'); // Count red rows

    if (tableRows.length === 0) return;

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
        const data = extractRowData(row);
        if (data) {
            payload.push(data);
            rowsArray.push(row);
        }
    });

    const success = await postToNinja(payload, rowsArray);

    if (success) {
        bulkBtn.innerHTML = "✅ Liste Validée";
        bulkBtn.className = "w3-button w3-light-grey w3-round-large";
    } else {
        bulkBtn.innerHTML = originalBtnText;
        bulkBtn.disabled = false;
    }
}