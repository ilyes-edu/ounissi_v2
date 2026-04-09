// static/js/salary_form.js
$(document).ready(function () {
    // Function to calculate the amount dynamically
    function calculateAmount() {
        const salaryItem = $('#id_salary_item').val();
        const base = $('#id_base').val();
        // Send a request to the server to calculate the amount
        $.get(
            '/calculate_amount/',
            { salary_item: salaryItem, base: base },
            function (data) {
                $('#id_amount').val(data.amount);
            }
        );
    }

    // Attach an event listener to the base field
    $('#id_base').on('input', calculateAmount);

    // Trigger the calculation when the page loads
    calculateAmount();
});
