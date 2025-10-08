// Fonction pour ajouter un marqueur sur la carte
function addMarker() {
    const iframe = document.getElementById('map-iframe');
    iframe.contentWindow.postMessage({ action: 'addMarker' }, '*');
}

// Fonction pour centrer la carte
function centerMap() {
    const iframe = document.getElementById('map-iframe');
    iframe.contentWindow.postMessage({ action: 'centerMap' }, '*');
}

// Fonction pour déplacer la carte vers une position spécifiée
function updatePosition() {
    const latitude = document.getElementById('latitude').value;
    const longitude = document.getElementById('longitude').value;

    if (!latitude || !longitude) {
        alert("Veuillez remplir la latitude et la longitude !");
        return;
    }

    const iframe = document.getElementById('map-iframe');
    iframe.contentWindow.postMessage({
        action: 'updatePosition',
        latitude: parseFloat(latitude),
        longitude: parseFloat(longitude)
    }, '*');
}
function testCommunication() {
    const iframe = document.getElementById('map-iframe');
    iframe.contentWindow.postMessage({ action: 'test' }, '*');
    console.log("Message envoyé à l'iframe : test");
}