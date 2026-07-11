document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".dropzone").forEach(function (zone) {
    var input = zone.querySelector("input[type='file']");
    if (!input) return;
    var filesLabel = zone.querySelector(".dropzone-files");

    function updateFilesLabel() {
      if (!filesLabel) return;
      if (input.files.length === 0) {
        filesLabel.textContent = "";
      } else if (input.files.length === 1) {
        filesLabel.textContent = input.files[0].name;
      } else {
        filesLabel.textContent = input.files.length + " Dateien ausgewählt";
      }
    }

    input.addEventListener("change", updateFilesLabel);
    updateFilesLabel();

    zone.addEventListener("click", function (e) {
      if (e.target !== input) {
        input.click();
      }
    });

    ["dragenter", "dragover"].forEach(function (evt) {
      zone.addEventListener(evt, function (e) {
        e.preventDefault();
        e.stopPropagation();
        zone.classList.add("dropzone-active");
      });
    });

    ["dragleave", "dragend", "drop"].forEach(function (evt) {
      zone.addEventListener(evt, function (e) {
        e.preventDefault();
        e.stopPropagation();
        zone.classList.remove("dropzone-active");
      });
    });

    zone.addEventListener("drop", function (e) {
      var dropped = e.dataTransfer.files;
      if (!dropped || !dropped.length) return;
      if (input.multiple) {
        input.files = dropped;
      } else {
        var dt = new DataTransfer();
        dt.items.add(dropped[0]);
        input.files = dt.files;
      }
      updateFilesLabel();
    });
  });
});
