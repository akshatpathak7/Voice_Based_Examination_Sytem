/* ============================================================
   Admin Dashboard – Client-side Logic
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {

    // ---- Show/hide registration number field based on role ----
    const roleSelect = document.getElementById('role-select');
    const regGroup = document.getElementById('reg-group');

    if (roleSelect && regGroup) {
        function toggleRegNo() {
            if (roleSelect.value === 'CANDIDATE') {
                regGroup.style.display = '';
                regGroup.querySelector('input').required = true;
            } else {
                regGroup.style.display = 'none';
                regGroup.querySelector('input').required = false;
                regGroup.querySelector('input').value = '';
            }
        }
        roleSelect.addEventListener('change', toggleRegNo);
        toggleRegNo();
    }
});


/* ---------- Confirmation helpers ---------- */

function confirmToggleStudent(name) {
    return confirm(
        `Change status for student "${name}"?\n\n` +
        `No exam data will be deleted. This only toggles login access.`
    );
}

function confirmRemoveAssignment() {
    return confirm('Remove this assignment?');
}
