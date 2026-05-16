// ÉDITSENSEI AI - After Effects Plugin Integration
// À inclure dans index.html

(function() {
    // Inclure le contrôleur
    #include "aeController.jsx"

    // Initialiser le panel
    var panel = this;
    
    if (panel instanceof Panel) {
        // Configuration du panel
        panel.text = "ÉDITSENSEI AI";
        
        // Créer la structure
        var group = panel.add("group");
        group.orientation = "column";
        group.alignChildren = ["fill", "fill"];
        
        // Ajouter les éléments du panel
        // C'est fait dans index.html
    }

    // Exposer les fonctions globales
    window.AEController = AEController;
    
    // Log d'initialisation
    $.writeln("ÉDITSENSEI AI Plugin loaded successfully");
})();
