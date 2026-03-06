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

function confirmDelete(name) {
    return confirm(
        `Are you sure you want to delete student "${name}"?\n\n` +
        `This will also remove their candidate profile, exam sessions, answers, and examiner assignments.`
    );
}

function confirmRemoveAssignment() {
    return confirm('Remove this assignment?');
}
