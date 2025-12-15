// Enhanced UI interactions for review interface
class ReviewUI {
  constructor() {
    this.initEventListeners();
    this.initTooltips();
  }

  initEventListeners() {
    document.addEventListener("keydown", (e) => {
      if (e.ctrlKey || e.metaKey) {
        switch (e.key) {
          case "a":
            e.preventDefault();
            if (typeof approveAllChanges === "function") approveAllChanges();
            break;
          case "r":
            e.preventDefault();
            if (typeof rejectAllChanges === "function") rejectAllChanges();
            break;
          case "Enter":
            e.preventDefault();
            if (typeof applyChanges === "function") applyChanges();
            break;
        }
      }
    });

    document.addEventListener("dblclick", (e) => {
      if (e.target && e.target.classList.contains("parsed-value")) {
        this.makeEditable(e.target);
      }
    });
  }

  initTooltips() {
    const tooltips = {
      "no-change": "Values are identical",
      "no-data": "No parsed value available",
      "new-data": "New value where original was empty",
      match: "Values match after normalization",
      "minor-diff": "Small differences (>90% similar)",
      "major-diff": "Significant differences (50-90% similar)",
      conflict: "Completely different values (<50% similar)",
    };

    document.querySelectorAll(".field-comparison").forEach((comparison) => {
      const status = comparison.querySelector(".field-status");
      if (!status) return;
      const statusKey = (status.textContent || "").trim();
      const key = statusKey.replace("_", "-");
      if (tooltips[key]) status.title = tooltips[key];
    });
  }

  makeEditable(element) {
    const originalValue = element.textContent;
    const input = document.createElement("input");
    input.type = "text";
    input.value = originalValue;
    input.className = "edit-input";

    input.addEventListener("blur", () => {
      element.textContent = input.value;
      element.classList.add("user-edited");
    });

    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") input.blur();
      if (e.key === "Escape") element.textContent = originalValue;
    });

    element.textContent = "";
    element.appendChild(input);
    input.focus();
    input.select();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  new ReviewUI();
});

