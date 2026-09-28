function confirmDelete() {

    return confirm(
        "Are you sure you want to delete this member?"
    );

}


// Automatically hide success messages

setTimeout(function () {

    const messages =
        document.querySelectorAll(".success, .alert");

    messages.forEach(function (message) {

        message.style.display = "none";

    });

}, 4000);