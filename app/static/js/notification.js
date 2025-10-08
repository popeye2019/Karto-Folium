(function () {
  const FIVE_MINUTES = 300000;

  const bodyDataset = document.body ? document.body.dataset : {};

  if (bodyDataset && bodyDataset.notificationRefresh === 'true') {
    const interval = parseInt(bodyDataset.notificationRefreshInterval || FIVE_MINUTES, 10) || FIVE_MINUTES;
    setInterval(() => {
      window.location.reload();
    }, interval);
  }

  if (typeof window.userId !== 'undefined') {
    const container = document.getElementById('notifications');
    if (!container) {
      return;
    }

    const interval = parseInt((bodyDataset && bodyDataset.notificationAjaxInterval) || FIVE_MINUTES, 10) || FIVE_MINUTES;

    function fetchNotifications() {
      fetch(`/notif/notifications/${window.userId}`)
        .then((response) => response.json())
        .then((data) => {
          container.innerHTML = '';

          if (!Array.isArray(data) || data.length === 0) {
            container.innerHTML = '<p>Aucune nouvelle notification.</p>';
            return;
          }

          data.forEach((notif) => {
            const div = document.createElement('div');
            div.innerHTML = `<p>${notif.message}</p>`;
            container.appendChild(div);
          });
        })
        .catch((error) => {
          console.error('Unable to fetch notifications', error);
        });
    }

    fetchNotifications();
    setInterval(fetchNotifications, interval);
  }
})();