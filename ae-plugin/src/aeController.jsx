// ÉDITSENSEI AI - After Effects Controller
// Contrôle After Effects via commandes ExtendScript

var AEController = {
    // Configuration
    config: {
        wsUrl: "ws://localhost:8001/ws/ae",
        reconnectDelay: 3000,
        maxReconnects: 5
    },

    // État
    state: {
        connected: false,
        currentLayer: null,
        reconnectAttempts: 0,
        socket: null
    },

    // Initialiser la connexion
    init: function() {
        alert("ÉDITSENSEI AI Plugin initialisé");
        this.connectWebSocket();
    },

    // Connexion WebSocket
    connectWebSocket: function() {
        var self = this;
        
        // Simulation WebSocket (ExtendScript n'a pas WebSocket natif)
        // On utilisera JSON sur fichier ou HTTP en fallback
        
        $.writeln("🔌 Tentative connexion ÉDITSENSEI...");
        
        // Envoyer un signal de prêt
        setTimeout(function() {
            self.broadcastReady();
        }, 1000);
    },

    // Signaler que le plugin est prêt
    broadcastReady: function() {
        $.writeln("✅ ÉDITSENSEI AI Prêt");
        this.state.connected = true;
        
        if (app.project && app.project.activeItem) {
            $.writeln("📽️  Composition active: " + app.project.activeItem.name);
        }
    },

    // Ajouter un effet à un calque
    addEffect: function(layerName, effectName, intensity) {
        try {
            var comp = app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                return { success: false, message: "Aucune composition active" };
            }

            var layer = this.getLayerByName(comp, layerName);
            if (!layer) {
                return { success: false, message: "Calque non trouvé: " + layerName };
            }

            var effect = layer.Effects.addProperty("ADBE " + this.getEffectCode(effectName));
            
            if (intensity !== undefined && effect) {
                // Ajuster l'intensité si possible
                if (effect.property("ADBE Glow-0001")) {
                    effect.property("ADBE Glow-0001").setValue(intensity * 100);
                }
            }

            $.writeln("✓ Effet ajouté: " + effectName + " → " + layerName);
            return { success: true, message: "Effet ajouté: " + effectName, data: { layer: layerName, effect: effectName } };

        } catch (err) {
            $.writeln("✗ Erreur ajout effet: " + err.message);
            return { success: false, message: "Erreur: " + err.message };
        }
    },

    // Ajouter une keyframe
    addKeyframe: function(layerName, propertyPath, value, time) {
        try {
            var comp = app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                return { success: false, message: "Aucune composition active" };
            }

            var layer = this.getLayerByName(comp, layerName);
            if (!layer) {
                return { success: false, message: "Calque non trouvé" };
            }

            var property = layer.property(propertyPath);
            if (!property) {
                return { success: false, message: "Propriété non trouvée: " + propertyPath };
            }

            // Ajouter keyframe à time
            property.setValueAtTime(time, value);
            
            $.writeln("✓ Keyframe ajoutée: " + propertyPath + " @ " + time + "s");
            return { success: true, message: "Keyframe ajoutée" };

        } catch (err) {
            $.writeln("✗ Erreur keyframe: " + err.message);
            return { success: false, message: "Erreur: " + err.message };
        }
    },

    // Appliquer un preset
    applyPreset: function(layerName, presetData) {
        try {
            var results = [];

            // Ajouter les effets
            for (var i = 0; i < presetData.effects.length; i++) {
                var effect = presetData.effects[i];
                var result = this.addEffect(layerName, effect.name, effect.intensity);
                results.push(result);
            }

            // Ajouter les keyframes
            for (var i = 0; i < presetData.keyframes.length; i++) {
                var kf = presetData.keyframes[i];
                var result = this.addKeyframe(layerName, kf.property, kf.value, kf.time);
                results.push(result);
            }

            $.writeln("✓ Preset appliqué: " + presetData.name);
            return { success: true, message: "Preset appliqué", results: results };

        } catch (err) {
            $.writeln("✗ Erreur preset: " + err.message);
            return { success: false, message: "Erreur: " + err.message };
        }
    },

    // Obtenir un calque par nom
    getLayerByName: function(comp, name) {
        for (var i = 1; i <= comp.numLayers; i++) {
            if (comp.layer(i).name === name) {
                return comp.layer(i);
            }
        }
        return null;
    },

    // Obtenir le code d'effet AfterEffects
    getEffectCode: function(effectName) {
        var effectMap = {
            "Glow": "Glow",
            "Blur": "ADBE Gaussian Blur",
            "Shake": "Shake Dimensions",
            "Chromatic": "Shift Channels",
            "RGB": "Channel Mix"
        };
        return effectMap[effectName] || effectName;
    },

    // Obtenir la composition active
    getActiveComposition: function() {
        if (app.project && app.project.activeItem instanceof CompItem) {
            return app.project.activeItem;
        }
        return null;
    },

    // Récupérer les calques
    getLayers: function() {
        var comp = this.getActiveComposition();
        if (!comp) return [];

        var layers = [];
        for (var i = 1; i <= comp.numLayers; i++) {
            layers.push({
                name: comp.layer(i).name,
                index: i,
                type: comp.layer(i).kind,
                selected: comp.layer(i).selected
            });
        }
        return layers;
    }
};

// Initialiser au chargement
AEController.init();
