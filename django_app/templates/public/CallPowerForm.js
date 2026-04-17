var CallPowerForm = function(formSelector, $) {
  this.$ = $;
  this.form = this.$(formSelector);
  this.locationField = this.$("{{ campaign.embed.location_sel|default:'#location_id' }}");
  this.phoneField = this.$("{{ campaign.embed.phone_sel|default:'#phone_id' }}");
  this.locateBy = "{{ campaign.locate_by|default:'' }}";
  this.scriptDisplay = "overlay";

  for (var option in window.CallPowerOptions || {}) {
    if (!Object.prototype.hasOwnProperty.call(window.CallPowerOptions, option)) {
      continue;
    }
    var setting = window.CallPowerOptions[option];
    var selectorFields = ["form", "locationField", "phoneField"];
    if ($.inArray(option, selectorFields) !== -1 && typeof setting === "string") {
      this[option] = this.$(setting);
    } else {
      this[option] = setting;
    }
  }

  this.form.on("submit.CallPower", this.$.proxy(this.makeCall, this));
  if (this.customCSS !== undefined) {
    this.$("head").append('<link rel="stylesheet" href="' + this.customCSS + '" />');
  }
};

CallPowerForm.prototype = function() {
  var createCallURL = "{{ base_url }}{% url 'call-create' %}";
  var campaignId = "{{ campaign.id }}";

  var getCountry = function() {
    return "{{ campaign.country_code|default:'US' }}";
  };

  var cleanUSZipcode = function(val) {
    if (val.length === 0) return undefined;
    return /(\d{5}([\-]\d{4})?)/.test(val) ? val : false;
  };

  var cleanCAPostal = function(val) {
    if (val.length === 0) return undefined;
    var valNospace = val.replace(/\W+/g, "");
    return /([ABCEGHJKLMNPRSTVXY]\d)([ABCEGHJKLMNPRSTVWXYZ]\d){2}/i.test(valNospace) ? valNospace : false;
  };

  var getLocation = function() {
    var countryCode = this.country();
    var locationVal = "";

    if (this.locationField.length === 1) {
      locationVal = this.locationField.val();
    } else if (this.locationField.length > 1) {
      this.locationField.each(function() {
        locationVal += " " + $(this).val();
      });
      locationVal = locationVal.trim();
    }

    if (this.locateBy === "postal") {
      if (countryCode === "US") return cleanUSZipcode(locationVal);
      if (countryCode === "CA") return cleanCAPostal(locationVal);
    }
    return locationVal;
  };

  var getPhone = function() {
    if (this.phoneField.length === 0) return undefined;
    return this.phoneField.val()
      .replace(/\s/g, "")
      .replace(/\(/g, "")
      .replace(/\)/g, "")
      .replace("+", "")
      .replace(/\-/g, "");
  };

  var onSuccess = function(response) {
    if (response.campaign === "archived") return this.onError(this.form, "This campaign is no longer active.");
    if (response.campaign !== "live") return this.onError(this.form, "This campaign is not live.");
    if (response.call !== "queued") return this.onError(this.form, "Could not start call.");

    if (this.phoneDisplay) {
      $(this.phoneDisplay).html(response.fromNumber);
    }

    if (this.scriptDisplay === "overlay") {
      var closeButton = '<button type="button" class="close" aria-label="Close"><span aria-hidden="true">&times;</span></button>';
      var closeText = this.overlayCloseText ? '<a class="closeText">' + this.overlayCloseText + "</a>" : "";
      var scriptOverlay = this.$(
        '<div class="overlay"><div class="modal">' + closeButton + (response.script || "") + closeText + "</div></div>"
      );
      this.$("body").append(scriptOverlay);
      if (scriptOverlay.overlay) {
        scriptOverlay.overlay();
      }
      scriptOverlay.css("visibility", "visible").addClass("shown");
    }

    if (this.scriptDisplay === "replace") {
      var scriptDiv = this.$('<div style="display:none;"></div>');
      scriptDiv.addClass(this.form.attr("class"));
      scriptDiv.attr("id", "callpower_script_response");
      scriptDiv.html(response.script || "<p>Calling now.</p>");
      scriptDiv.insertAfter(this.form);
      this.form.slideUp();
      scriptDiv.slideDown();
    }

    if (this.scriptDisplay === "redirect") {
      this.redirectAfter = response.redirect;
    }

    if (this.scriptDisplay === "alert") {
      var message = this.$(response.script || "");
      alert(message.text() || "Calling now.");
    }

    if (typeof this.customJS !== "undefined") {
      if (typeof this.customJS === "string") {
        eval(this.customJS);
      } else if (typeof this.customJS === "function") {
        this.customJS();
      }
    }

    return true;
  };

  var onError = function(element, message) {
    if (element !== undefined && element.addClass) {
      element.addClass("has-error");
    }
    console.error("CallPower error: " + message);
    return false;
  };

  var makeCall = function(event) {
    if (event !== undefined) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }

    if (this.locationField.length && !this.location()) {
      return this.onError(this.locationField, "Invalid location");
    }
    if (this.phoneField.length && !this.phone()) {
      return this.onError(this.phoneField, "Invalid phone number");
    }

    this.$.ajax(createCallURL, {
      method: "GET",
      data: {
        campaignId: campaignId,
        userLocation: this.location(),
        userPhone: this.phone(),
        userCountry: this.country()
      },
      statusCode: {
        429: function() {
          alert("Sorry, you have made too many requests in the last hour. Please try again later.");
        }
      }
    })
      .done(this.$.proxy(this.onSuccess, this))
      .then(this.$.proxy(function() {
        this.form.off("submit.CallPower");
        if (this.scriptDisplay === "overlay") {
          var scriptOverlay = this.$(".overlay");
          scriptOverlay.on("hide", this.$.proxy(this.formSubmit, this));
          scriptOverlay.on("click", this.$.proxy(function(e) {
            var target = $(e.target);
            if (target.hasClass(scriptOverlay.attr("class")) || target.hasClass("close") || target.hasClass("closeText")) {
              return scriptOverlay.trigger("hide");
            }
          }, this));
        } else if (this.scriptDisplay === "redirect" && this.redirectAfter) {
          window.location.replace(this.redirectAfter);
        } else if (this.scriptDisplay !== "replace") {
          this.formSubmit();
        }
      }, this))
      .fail(this.$.proxy(this.onError, this, this.form, "Sorry, there was an error making the call"));

    return false;
  };

  var formSubmit = function() {
    window.setTimeout(this.$.proxy(function() {
      this.form.trigger("submit");
    }, this), this.submitDelay || 0);
  };

  var publicApi = {
    getCountry: getCountry,
    getLocation: getLocation,
    getPhone: getPhone,
    onError: onError,
    onSuccess: onSuccess,
    makeCall: makeCall,
    formSubmit: formSubmit
  };
  publicApi.country = publicApi.getCountry;
  publicApi.location = publicApi.getLocation;
  publicApi.phone = publicApi.getPhone;
  return publicApi;
}();
