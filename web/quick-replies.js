// Standalone UI demonstration: no implicit network fetch or private-data access.
const source = document.querySelector('#job-spec');
const status = document.querySelector('#quick-reply-status');
for (const control of document.querySelectorAll('[data-action]')) {
  control.addEventListener('click', () => {
    if (control.dataset.action === 'job-spec') {
      source.focus();
      status.textContent = 'Paste a job description. A real role comparison must first extract the actual requirements, then map each to approved evidence or an explicit gap.';
    } else {
      status.textContent = 'Synthetic trace available in fixtures/public-trace.json in the reference repository. This is not a live private-system log.';
    }
  });
}
