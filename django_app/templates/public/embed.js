{% load static %}
{% include "public/CallPowerForm.js" with campaign=campaign base_url=base_url %}

var main = function($) {
  var callPowerForm;
  if (window.CallPowerOptions && window.CallPowerOptions.form) {
    callPowerForm = new CallPowerForm(window.CallPowerOptions.form, $);
  } else {
    callPowerForm = new CallPowerForm("form", $);
  }

  if (window.CallPowerOptions && window.CallPowerOptions.scriptDisplay === "overlay" && !$.overlay) {
    $.getScript("{{ base_url }}{% static 'embed/overlay.js' %}");
    $("head").append('<link rel="stylesheet" href="{{ base_url }}{% static "embed/overlay.css" %}" />');
  }

  if (window.CallPowerOptions && typeof window.CallPowerOptions.customOnload !== "undefined") {
    if (typeof window.CallPowerOptions.customOnload === "function") {
      window.CallPowerOptions.customOnload();
    }
  }
};

function versionCmp(a, b) {
  var pa = a.split(".");
  var pb = b.split(".");
  for (var i = 0; i < 3; i++) {
    var na = Number(pa[i]);
    var nb = Number(pb[i]);
    if (na > nb) return 1;
    if (nb > na) return -1;
    if (!isNaN(na) && isNaN(nb)) return 1;
    if (isNaN(na) && !isNaN(nb)) return -1;
  }
  return 0;
}

function getScript(url, success, cors) {
  var script = document.createElement("script");
  script.src = url;
  if (cors) {
    script.crossOrigin = cors;
  }
  var head = document.getElementsByTagName("head")[0];
  var done = false;
  script.onload = script.onreadystatechange = function() {
    if (!done && (!this.readyState || this.readyState === "loaded" || this.readyState === "complete")) {
      done = true;
      success();
      script.onload = script.onreadystatechange = null;
      head.removeChild(script);
    }
  };
  head.appendChild(script);
}

if (typeof window.jQuery === "undefined") {
  getScript("//cdnjs.cloudflare.com/ajax/libs/jquery/1.12.4/jquery.js", function() {
    return main(jQuery);
  });
} else if (versionCmp(window.jQuery.fn.jquery, "1.7.0") < 0) {
  getScript("//cdnjs.cloudflare.com/ajax/libs/jquery/1.12.4/jquery.min.js", function() {
    jQuery.noConflict();
    return main(jQuery);
  });
} else {
  jQuery(document).ready(main);
}
