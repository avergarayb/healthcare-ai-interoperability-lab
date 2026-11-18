(function () {
  const tabs = Array.from(document.querySelectorAll("[data-tab]"));
  const panels = Array.from(document.querySelectorAll("[data-panel]"));
  if (!tabs.length) return;

  function activate(id) {
    tabs.forEach(function (tab) {
      const selected = tab.getAttribute("data-tab") === id;
      tab.setAttribute("aria-selected", selected ? "true" : "false");
      tab.tabIndex = selected ? 0 : -1;
    });
    panels.forEach(function (panel) {
      panel.hidden = panel.getAttribute("data-panel") !== id;
    });
  }

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () { activate(tab.getAttribute("data-tab")); });
  });
  const list = document.querySelector("[role='tablist']");
  if (list) {
    list.addEventListener("keydown", function (event) {
      const index = tabs.indexOf(document.activeElement);
      if (index < 0) return;
      let next = index;
      if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
      else if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
      else return;
      event.preventDefault();
      tabs[next].focus();
      activate(tabs[next].getAttribute("data-tab"));
    });
  }
  function fromHash() {
    const id = (location.hash || "").replace("#", "");
    if (tabs.some(function (tab) { return tab.getAttribute("data-tab") === id; })) {
      activate(id);
    }
  }

  window.addEventListener("hashchange", fromHash);
  fromHash();
})();
