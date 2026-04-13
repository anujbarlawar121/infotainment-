document.addEventListener("DOMContentLoaded", () => {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";

    const themeToggle = document.getElementById("themeToggle");
    const savedTheme = localStorage.getItem("theme") || "dark";
    document.documentElement.setAttribute("data-bs-theme", savedTheme);

    if (themeToggle) {
        themeToggle.addEventListener("click", () => {
            const current = document.documentElement.getAttribute("data-bs-theme") || "dark";
            const next = current === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-bs-theme", next);
            localStorage.setItem("theme", next);
        });
    }

    if (window.dashboardStats) {
        const commonOptions = {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true } },
        };

        const categoryChart = document.getElementById("categoryChart");
        if (categoryChart) {
            new Chart(categoryChart, {
                type: "bar",
                data: {
                    labels: window.dashboardStats.category_labels,
                    datasets: [{
                        data: window.dashboardStats.category_values,
                        backgroundColor: ["#ff7a18", "#23c4a8", "#5fa8ff", "#ffd166", "#ef476f", "#9b5de5"],
                        borderRadius: 12,
                    }],
                },
                options: commonOptions,
            });
        }

        const searchChart = document.getElementById("searchChart");
        if (searchChart) {
            new Chart(searchChart, {
                type: "doughnut",
                data: {
                    labels: window.dashboardStats.search_labels,
                    datasets: [{
                        data: window.dashboardStats.search_values,
                        backgroundColor: ["#23c4a8", "#ff7a18", "#5fa8ff", "#ffd166", "#ef476f"],
                    }],
                },
            });
        }
    }

    const trackLinks = document.querySelectorAll(".track-content-link");
    if (trackLinks.length && csrfToken) {
        trackLinks.forEach((link) => {
            link.addEventListener("click", () => {
                const payload = {
                    interaction_type: "click",
                    source_page: link.dataset.sourcePage || "",
                    category: link.dataset.category || "",
                    title: link.dataset.title || "",
                    provider: link.dataset.provider || "",
                    domain: link.dataset.domain || "",
                    url: link.getAttribute("href") || "",
                    score: link.dataset.score || "",
                    mood: link.dataset.mood || "",
                    interests: link.dataset.interests || "",
                };

                fetch("/api/interactions", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRF-Token": csrfToken,
                    },
                    body: JSON.stringify(payload),
                    keepalive: true,
                }).catch(() => {});
            });
        });
    }
});
