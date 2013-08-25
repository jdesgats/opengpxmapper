requirejs.config({
  baseUrl: 'static/js',
  shim: {
    "lib/zepto": { exports: "$" },
    "lib/underscore": { exports: "_" },
    "lib/aristochart": { exports: "Aristochart" },
    "lib/leaflet.polylineDecorator": [ "lib/leaflet" ],
  }
});

requirejs(["app"], function(app) {
  app();
});