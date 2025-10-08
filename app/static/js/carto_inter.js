window.addEventListener('message', function(event) {
    const data = event.data;

    if (data.action === 'addMarker') {
        alert(`Ajouter un marqueur depuis l'iframe : ${data.source}`);
}  else if (data.action === 'centerMap') {
alert(`Centrer la carte depuis l'iframe : ${data.source}`);
} else if (data.action === 'updatePosition') {
alert(`Déplacer la carte vers : ${data.latitude}, ${data.longitude}, depuis l'iframe : ${data.source}`);
} else if (data.action === 'test') {
alert(`Communication avec l'iframe réussie ! Source : ${data.source}`);
}
});