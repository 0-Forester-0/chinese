document.addEventListener('DOMContentLoaded', function () {
    const ctx = document.getElementById('progressChart');
    if (!ctx) {
        return;
    }

    let stats;
    try {
        stats = JSON.parse(document.getElementById('stats-data').textContent) || {
            HSK1: { best_percentage: 0 },
            HSK2: { best_percentage: 0 },
            HSK3: { best_percentage: 0 }
        };
    } catch (e) {
        console.error('Error parsing stats JSON:', e);
        stats = {
            HSK1: { best_percentage: 0 },
            HSK2: { best_percentage: 0 },
            HSK3: { best_percentage: 0 }
        };
    }

    new Chart(ctx.getContext('2d'), {
        type: 'bar',
        data: {
            labels: ['HSK1', 'HSK2', 'HSK3'],
            datasets: [{
                label: 'Лучший процент освоения',
                data: [
                    stats.HSK1.best_percentage || 0,
                    stats.HSK2.best_percentage || 0,
                    stats.HSK3.best_percentage || 0
                ],
                backgroundColor: ['#007bff', '#28a745', '#dc3545'],
                borderColor: ['#0056b3', '#218838', '#c82333'],
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: {
                        display: true,
                        text: 'Процент (%)'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
});