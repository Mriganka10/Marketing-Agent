const leadForm = document.querySelector(".lead-form");
const sessionId = (() => {
  const key = "marketing_agent_session";
  const existing = window.sessionStorage?.getItem(key);
  if (existing) return existing;
  const value = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
  window.sessionStorage?.setItem(key, value);
  return value;
})();

async function trackEvent(eventType, metadata = {}) {
  if (!leadForm) return;
  await fetch("/api/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    keepalive: true,
    body: JSON.stringify({
      campaign_id: leadForm.dataset.campaign,
      page_id: leadForm.dataset.page,
      event_type: eventType,
      session_id: sessionId,
      path: window.location.pathname,
      referrer: document.referrer || null,
      event_metadata: metadata,
    }),
  }).catch(() => undefined);
  if (typeof gtag === "function") {
    gtag("event", eventType, metadata);
  }
}

let formStarted = false;
let scrollTracked = false;

leadForm?.addEventListener("focusin", () => {
  if (!formStarted) {
    formStarted = true;
    trackEvent("form_start", { form: "lead_capture" });
  }
});

leadForm?.querySelector("button")?.addEventListener("click", () => {
  trackEvent("cta_click", { cta: "lead_form_submit" });
});

window.addEventListener("scroll", () => {
  if (scrollTracked) return;
  const progress = (window.scrollY + window.innerHeight) / Math.max(document.body.scrollHeight, 1);
  if (progress >= 0.75) {
    scrollTracked = true;
    trackEvent("scroll_75", { depth: 75 });
  }
}, { passive: true });

leadForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const status = form.querySelector(".form-status");
  const response = await fetch("/api/leads", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      campaign_id: form.dataset.campaign,
      page_id: form.dataset.page,
      name: data.get("name"),
      email: data.get("email"),
      company: data.get("company"),
      message: data.get("message"),
      source: "public_landing_page",
    }),
  });
  status.textContent = response.ok
    ? "Thanks. The team will follow up shortly."
    : "Something went wrong. Please try again.";
  if (response.ok) {
    await trackEvent("form_submit", { form: "lead_capture" });
    form.reset();
  }
});
