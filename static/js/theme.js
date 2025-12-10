function toggleTheme() {
    let body = document.body;

    if (body.classList.contains("light")) {
        body.classList.remove("light");
        body.classList.add("dark");
        localStorage.setItem("theme", "dark");
    } else {
        body.classList.remove("dark");
        body.classList.add("light");
        localStorage.setItem("theme", "light");
    }
}

// Load saved theme
window.onload = function () {
    let savedTheme = localStorage.getItem("theme") || "light";
    document.body.classList.add(savedTheme);
};
