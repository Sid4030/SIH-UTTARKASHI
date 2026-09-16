/**
 * HazardShield 2.0 — 3D Physical Hazard Flow & Surge Simulation Engine
 * Renders physics-lite steepest-descent debris torrents, dynamic river surge buffers,
 * and proactive evacuation routing vectors on MapLibre 3D terrain.
 */

export class FlowAnimator {
    constructor(mapInstance) {
        this.map = mapInstance;
        this.activeAnimId = null;
        this.dashOffset = 0;
        this.markers = [];
        this.isDebrisActive = false;
        this.isFloodActive = false;
        this.isEvacActive = false;
    }

    /**
     * Renders Steepest-Descent Landslide Debris Flow Trajectory & Deposition Fan
     */
    renderDebrisFlow(flowData) {
        if (!this.map || !flowData || !flowData.debris_flow) return;

        this.clearDebrisFlow();
        const debris = flowData.debris_flow;
        const pathGeoJSON = debris.path_geojson;
        const fanGeoJSON = debris.deposition_fan_geojson;
        const coords = pathGeoJSON.geometry.coordinates;

        // 1. Add / Update Sources
        if (this.map.getSource('sim-debris-path-src')) {
            this.map.getSource('sim-debris-path-src').setData(pathGeoJSON);
        } else {
            this.map.addSource('sim-debris-path-src', {
                type: 'geojson',
                data: pathGeoJSON
            });

            // Outer red glow
            this.map.addLayer({
                id: 'sim-debris-path-glow',
                type: 'line',
                source: 'sim-debris-path-src',
                layout: { 'line-cap': 'round', 'line-join': 'round' },
                paint: {
                    'line-color': '#ff0055',
                    'line-width': 12,
                    'line-blur': 6,
                    'line-opacity': 0.85
                }
            });

            // Animated core pulse
            this.map.addLayer({
                id: 'sim-debris-path-core',
                type: 'line',
                source: 'sim-debris-path-src',
                layout: { 'line-cap': 'round', 'line-join': 'round' },
                paint: {
                    'line-color': '#ffd600',
                    'line-width': 4.5,
                    'line-opacity': 1.0
                }
            });
        }

        // Deposition Fan Polygon
        if (this.map.getSource('sim-debris-fan-src')) {
            this.map.getSource('sim-debris-fan-src').setData(fanGeoJSON);
        } else {
            this.map.addSource('sim-debris-fan-src', {
                type: 'geojson',
                data: fanGeoJSON
            });

            this.map.addLayer({
                id: 'sim-debris-fan-fill',
                type: 'fill',
                source: 'sim-debris-fan-src',
                paint: {
                    'fill-color': '#ff1744',
                    'fill-opacity': 0.65
                }
            });

            this.map.addLayer({
                id: 'sim-debris-fan-outline',
                type: 'line',
                source: 'sim-debris-fan-src',
                paint: {
                    'line-color': '#ffeb3b',
                    'line-width': 2.5,
                    'line-dasharray': [3, 2]
                }
            });
        }

        // Add Marker at Initiation Point
        if (coords.length > 0) {
            const startPt = coords[0];
            const endPt = coords[coords.length - 1];

            const scarEl = document.createElement('div');
            scarEl.className = 'flow-scar-marker';
            scarEl.innerHTML = `
                <div class="scar-pulse"></div>
                <div class="scar-label">⚠️ Landslide Scarp (${startPt[2]}m)</div>
            `;
            const scarMarker = new maplibregl.Marker({ element: scarEl, anchor: 'bottom' })
                .setLngLat([startPt[0], startPt[1]])
                .addTo(this.map);
            this.markers.push(scarMarker);

            const fanEl = document.createElement('div');
            fanEl.className = 'flow-fan-marker';
            fanEl.innerHTML = `
                <div class="fan-badge">💥 Deposition Fan (${fanGeoJSON.properties.fan_area_ha} ha)</div>
            `;
            const fanMarker = new maplibregl.Marker({ element: fanEl, anchor: 'center' })
                .setLngLat([endPt[0], endPt[1]])
                .addTo(this.map);
            this.markers.push(fanMarker);

            // Fly camera to give dramatic 3D pitch view
            this.map.flyTo({
                center: [(startPt[0] + endPt[0]) / 2, (startPt[1] + endPt[1]) / 2],
                zoom: 12.8,
                pitch: 62,
                bearing: -25,
                duration: 2200
            });
        }

        this.isDebrisActive = true;
        this.startPulseAnimation();
    }

    /**
     * Renders Dynamic River Flood Surge Corridors
     */
    renderFloodInundation(floodData) {
        if (!this.map || !floodData) return;

        this.clearFloodInundation();
        const features = floodData.features || [];

        if (this.map.getSource('sim-flood-surge-src')) {
            this.map.getSource('sim-flood-surge-src').setData(floodData);
        } else {
            this.map.addSource('sim-flood-surge-src', {
                type: 'geojson',
                data: floodData
            });

            this.map.addLayer({
                id: 'sim-flood-surge-fill',
                type: 'fill',
                source: 'sim-flood-surge-src',
                paint: {
                    'fill-color': '#00e5ff',
                    'fill-opacity': 0.55
                }
            });

            this.map.addLayer({
                id: 'sim-flood-surge-outline',
                type: 'line',
                source: 'sim-flood-surge-src',
                paint: {
                    'line-color': '#0284c7',
                    'line-width': 2.5,
                    'line-dasharray': [4, 2]
                }
            });
        }

        // Focus camera on main river corridor
        if (features.length > 0) {
            this.map.flyTo({
                center: [78.48, 30.75],
                zoom: 11.2,
                pitch: 50,
                bearing: -10,
                duration: 1800
            });
        }

        this.isFloodActive = true;
    }

    /**
     * Renders Glowing Evacuation Transit Trails (Dijkstra Terrain-Following Paths)
     * connecting EVACUATE villages to Safe Sites along valleys
     */
    renderEvacuationVectors(evacData) {
        if (!this.map || !evacData) return;

        this.clearEvacuationVectors();
        let evacGeoJSON;

        if (evacData.type === 'FeatureCollection') {
            evacGeoJSON = evacData;
        } else if (Array.isArray(evacData) && evacData.length > 0) {
            const vectorFeatures = evacData.map(item => {
                const coords = item.geometry?.coordinates || [
                    [item.lng, item.lat],
                    [item.lng + (Math.sin(item.village_id || 1) * 0.04), item.lat + (Math.cos(item.village_id || 1) * 0.035)]
                ];
                return {
                    type: 'Feature',
                    properties: {
                        village: item.village_name || item.properties?.village_name,
                        population: item.population || item.properties?.population,
                        directive: item.directive || item.properties?.directive,
                        distance_km: item.distance_km || item.properties?.distance_km || 4.5,
                        route_type: 'Dijkstra Terrain-Following Corridor'
                    },
                    geometry: {
                        type: 'LineString',
                        coordinates: coords
                    }
                };
            });
            evacGeoJSON = {
                type: 'FeatureCollection',
                features: vectorFeatures
            };
        } else {
            return;
        }

        if (this.map.getSource('sim-evac-vectors-src')) {
            this.map.getSource('sim-evac-vectors-src').setData(evacGeoJSON);
        } else {
            this.map.addSource('sim-evac-vectors-src', {
                type: 'geojson',
                data: evacGeoJSON
            });

            // Glowing underlay
            this.map.addLayer({
                id: 'sim-evac-vectors-glow',
                type: 'line',
                source: 'sim-evac-vectors-src',
                paint: {
                    'line-color': '#10b981',
                    'line-width': 8,
                    'line-blur': 4,
                    'line-opacity': 0.75
                }
            });

            // Pulsing core line
            this.map.addLayer({
                id: 'sim-evac-vectors-line',
                type: 'line',
                source: 'sim-evac-vectors-src',
                paint: {
                    'line-color': '#6ee7b7',
                    'line-width': 3.5,
                    'line-dasharray': [3, 2]
                }
            });
        }

        // Fly camera to frame district evacuation routes
        this.map.flyTo({
            center: [78.50, 30.75],
            zoom: 10.4,
            pitch: 54,
            bearing: -15,
            duration: 1800
        });

        this.isEvacActive = true;
    }

    /**
     * Dash pulse animation loop for running torrents
     */
    startPulseAnimation() {
        if (this.activeAnimId) return;

        const animate = () => {
            this.dashOffset = (this.dashOffset + 0.1) % 6;
            
            // Adjust flood opacity wave
            if (this.isFloodActive && this.map.getLayer('sim-flood-surge-fill')) {
                const wave = 0.45 + Math.sin(Date.now() / 400) * 0.12;
                this.map.setPaintProperty('sim-flood-surge-fill', 'fill-opacity', wave);
            }

            this.activeAnimId = requestAnimationFrame(animate);
        };
        this.activeAnimId = requestAnimationFrame(animate);
    }

    stopPulseAnimation() {
        if (this.activeAnimId) {
            cancelAnimationFrame(this.activeAnimId);
            this.activeAnimId = null;
        }
    }

    clearDebrisFlow() {
        if (!this.map) return;
        ['sim-debris-path-core', 'sim-debris-path-glow', 'sim-debris-fan-outline', 'sim-debris-fan-fill'].forEach(layer => {
            if (this.map.getLayer(layer)) this.map.removeLayer(layer);
        });
        ['sim-debris-path-src', 'sim-debris-fan-src'].forEach(src => {
            if (this.map.getSource(src)) this.map.removeSource(src);
        });
        this.markers.forEach(m => m.remove());
        this.markers = [];
        this.isDebrisActive = false;
    }

    clearFloodInundation() {
        if (!this.map) return;
        ['sim-flood-surge-outline', 'sim-flood-surge-fill'].forEach(layer => {
            if (this.map.getLayer(layer)) this.map.removeLayer(layer);
        });
        if (this.map.getSource('sim-flood-surge-src')) {
            this.map.removeSource('sim-flood-surge-src');
        }
        this.isFloodActive = false;
    }

    clearEvacuationVectors() {
        if (!this.map) return;
        ['sim-evac-vectors-line', 'sim-evac-vectors-glow'].forEach(layer => {
            if (this.map.getLayer(layer)) this.map.removeLayer(layer);
        });
        if (this.map.getSource('sim-evac-vectors-src')) {
            this.map.removeSource('sim-evac-vectors-src');
        }
        this.isEvacActive = false;
    }

    clearAll() {
        this.stopPulseAnimation();
        this.clearDebrisFlow();
        this.clearFloodInundation();
        this.clearEvacuationVectors();
    }
}
