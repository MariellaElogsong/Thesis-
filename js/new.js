document.addEventListener('DOMContentLoaded', function () {
    const form = document.querySelector('form');
    const fileInput = document.getElementById('csvFile');

    form.addEventListener('submit', function (e) {
        if (!fileInput.value) {
            e.preventDefault();
            alert('Please select a CSV file to upload.');
        } else {
            alert('File uploaded successfully!');
            // The form will submit if a file is selected
        }
    });
});