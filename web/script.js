let ctx = document.getElementById('myChart').getContext('2d');
let chart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'CO2 ppm',
            data: [],
            borderColor: 'rgba(75, 192, 192, 1)',
            tension: 0.1
        }]
    },
    options: {
        scales: {
            x: {
                reverse: true,
                title: {
                    display: true,
                    text: 'Minutes'
                }
            },
            y: {
                title: {
                    display: true,
                    text: 'CO2 ppm'
                }
            }
        }
    }
});

function fetchData() {
    fetch('/history.json')
        .then(response => response.json())
        .then(data => {
            if (data.length > 120) {
                chart.data.labels = data.map((_, i) => -i / 60);
                chart.options.scales.x.title.text = 'Hours';
            } else {
                chart.data.labels = data.map((_, i) => -i);
                chart.options.scales.x.title.text = 'Minutes';
            }
            chart.data.datasets[0].data = data;
            chart.update();
        });
}

fetchData();
setInterval(fetchData, 60000);
