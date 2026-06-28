document.querySelector(".lead-form")?.addEventListener("submit", async (event) => {
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
  if (response.ok) form.reset();
});

