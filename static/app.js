
async function logout() {
  await fetch("/api/logout", {method: "POST"});
  location.href = "/";
}
