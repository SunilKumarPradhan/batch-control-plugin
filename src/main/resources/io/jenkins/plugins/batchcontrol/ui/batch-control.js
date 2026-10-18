/*
 * #93: rejecting a run request is final, so the Reject button on the request
 * page asks for confirmation first, with core's confirmation dialog
 * (window.dialog.confirm — the same dialog l:confirmationLink uses). The form
 * posts only after the approver confirms; Cancel and Escape post nothing.
 * Without JavaScript, or when core's dialog is unavailable, the button submits
 * the form exactly as before.
 */
document.addEventListener("click", function (event) {
  var target = event.target;
  var button =
    target instanceof Element
      ? target.closest("[data-batch-control-confirm-reject]")
      : null;
  if (!button || button.disabled) {
    return;
  }
  if (!window.dialog || typeof window.dialog.confirm !== "function") {
    return; // No core dialog: submit the form as before.
  }
  event.preventDefault();
  var form = button.form;
  window.dialog
    .confirm("Reject this run request?", {
      message: "The request will be rejected. This cannot be undone.",
      type: "destructive",
      okText: "Reject request",
    })
    .then(
      function () {
        if (form) {
          // Submits with this button as the submitter, so its formaction
          // (…/reject) is honoured and core still appends the crumb.
          form.requestSubmit(button);
        }
      },
      function () {
        // Cancelled or dismissed: post nothing.
      },
    );
});
