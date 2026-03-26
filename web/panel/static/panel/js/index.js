(function () {
    document.addEventListener('DOMContentLoaded', function () {
        // Init sidenav
        M.Sidenav.init(document.querySelectorAll('.sidenav'), {});

        // Init selects
        M.FormSelect.init(document.querySelectorAll('select'), {});
    });
})();