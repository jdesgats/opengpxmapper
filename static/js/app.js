define([
  // 3rd party
  "lib/zepto", 
  "lib/underscore", 
  "lib/leaflet", 
  "lib/aristochart",
  // application
  "graph",
  // plugins
  "lib/leaflet.polylineDecorator",
],
function($, _, L, Aristochart, graph) {
  return function() {
    var colors = [
      '#CF5300', // orange
      '#4D1E00', // brown
      '#333333', // grey
      '#000044', // dark blue
      '#CC0000', // red
      '#6600CC', // purple
      '#CA278C', // dark pink
      '#3A5F0B', // green
    ];
    var color_index = 0;
    var map;
    var tracks = { };           // track_id => track_info
    var item_tmpl = _.template(document.getElementById("track-summary-template").text);
    var graphMarker;
    
    var display_track = function(track) {
      if (track.points) {
        // we got points in cache, display thme
        var color = colors[(color_index++) % colors.length];
        var line = L.polyline(track.points, { color: color });
        var decorator = L.polylineDecorator(line, {
          patterns: [{
            offset: 0, 
            repeat: '100px', 
            symbol: new L.Symbol.ArrowHead({
              pixelSize: 10,
              pathOptions: { color: color, opacity: 0.8 }
            })
          }]
        });
        track.layer = L.layerGroup([ line, decorator ]).addTo(map);
        track.item.css("border-left", "6px solid "+color); // FIXME: use CSS
      } else {
        $.get("/tracks/"+track.track_id+"/points", function(data, status, xhr) {
          track.points = _.map(data, function(p) { return L.latLng(p.lat, p.lon); });
          display_track(track);
        });
      }
    };

    var hide_track = function(track) {
      if (track.layer) {
        map.removeLayer(track.layer);
        track.layer = undefined;
        track.item.css("border-left", null);
      }
    };
    
    var toggle_track = function(e) {
      var track = tracks[parseInt($(this).data("id"))];
      (track.layer ? hide_track : display_track)(track);
    };
    
    var moveMarker = function(evt) {
      var latlng = L.latLng(evt.detail.lat, evt.detail.lon);
      if (graphMarker === undefined) {
        graphMarker = L.marker(latlng).addTo(map);
      } else {
        graphMarker.setLatLng(latlng);
      }
    }
    
    var removeMarker = function() {
      if (graphMarker !== undefined) {
        map.removeLayer(graphMarker);
        graphMarker = undefined;
      }
    }
    
    var toggle_graphs = function(e) {
      var details = $(".track-details", this);
      if (details.hasClass("track-details-hidden")) {
        details.removeClass("track-details-hidden");
        if (details.find("canvas").length == 0)
        {
          var track = tracks[parseInt($(this).data("id"))];
          $.get("/tracks/"+track.track_id+"/downsampled", { method: "time", points: 100 }, function(data, status, xhr) {
            console.log("Got " + data.length + " downsampled points");
            _.each([graph.speedGraph, graph.altGraph], function(f) {
              var graph = f(details[0], data);
              $(graph.canvas).on("pointselected", moveMarker)
                             .on("mouseout", removeMarker);
            })
          }, "json");
        }
      } else {
        details.addClass("track-details-hidden");
      }
    }

    var init = function(data, status, xhr) {
      // parse data
      for(var i=0; i<data.length; i++) {
        var t = data[i];
        t.start_date = new Date(t.start_date);
        t.end_date = new Date(t.end_date);
        t.duration = (t.end_date.getTime() - t.start_date.getTime()) / 1000;
        tracks[t.track_id] = t;
      }

      // render
      var container = document.getElementById("nav");
      _.chain(tracks).values().sortBy(function(t) { return -t.start_date.getTime() }).each(function(t) {
        tracks[t.track_id].item = $(item_tmpl({
          track_id: t.track_id,
          length: Math.round(t.distance / 1000),
          date: t.start_date.toLocaleDateString(), //TODO: print localized day, ... (standard not yet implemented)
          title: t.name,
          desc: t.desc || "",
          duration: Math.floor(t.duration / 3600) + "h" + Math.floor((t.duration % 3600) / 60) + "min",
          uphill: Math.round(t.uphill),
          downhill: Math.round(t.downhill),
          speed: Math.round((3.6 * t.distance) / t.duration),
        })).appendTo(container)
           .on("click", toggle_track)
           .on("click", toggle_graphs);
      });
      
      // map
      var lat_min = _.chain(tracks).pluck("lat_min").min().value()
      var lat_max = _.chain(tracks).pluck("lat_max").max().value()
      var lon_min = _.chain(tracks).pluck("lon_min").min().value()
      var lon_max = _.chain(tracks).pluck("lon_max").max().value()
      
      map = L.map('main');
      map.fitBounds([[lat_min, lon_min], [lat_max, lon_max]]);
      L.tileLayer('http://{s}.tile.osm.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
      }).addTo(map);
      L.control.scale({ position: 'bottomleft', metric: true, imperial: false }).addTo(map);
      
      //FIXME: debugging only
      window.map = map;
    };

    
    $.get("/tracks", init);
  };
});