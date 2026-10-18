/*
 * #93: rejecting a run request is final, so the Reject button on the request
 * page asks for confirmation first, with core's confirmation dialog
 * (window.dialog.confirm — the same dialog l:confirmationLink uses). The form
 * posts only after the approver confirms; Cancel and Escape post nothing.
 * When the comment is blank the server refuses the rejection anyway, so the
 * dialog is skipped and the server's error shows directly. Without
 * JavaScript, or when core's dialog is unavailable, the button submits
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
  var form = button.form;
  // #93 (owner review): when the comment is blank the server refuses the
  // rejection anyway — skip the dialog and let the server's error show directly.
  var commentBox = form
    ? form.querySelector('textarea[name="comment"], input[name="comment"]:not([type="hidden"])')
    : null;
  var comment = commentBox ? commentBox.value || "" : "";
  if (comment.trim() === "") {
    return; // Submit as before; the server refuses with its message.
  }
  if (!window.dialog || typeof window.dialog.confirm !== "function") {
    return; // No core dialog: submit the form as before.
  }
  event.preventDefault();
  window.dialog
    .confirm("Reject this run request?", {
      message: "Rejection is final for this request; a rejected request cannot be reopened.",
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
