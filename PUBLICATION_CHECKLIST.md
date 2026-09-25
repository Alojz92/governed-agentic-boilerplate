# Public release / no-data-leaks checklist

- [ ] Owner approves public repository creation and MIT license for these newly authored files.
- [ ] Git history begins with this generated reference implementation, not a clone of a private repository.
- [ ] All examples use `example/workflow-demo`, synthetic identities and fake SHA values.
- [ ] Check tracked files **and history** for secrets, credentials, customer details, local paths, private repository names/topology, source IP, logs and commercial telemetry.
- [ ] Do not publish real Desktop Commander tool schemas, authenticated API headers, private prompts or policy/routing algorithms.
- [ ] Confirm third-party license constraints if replacing reference code with any dependencies or copied snippets.
- [ ] Run unit tests, security review and optional private secret scanner before publication.
- [ ] UI's video and public URL remain labelled *coming soon* until a separately approved, sanitized screencast or deployed repository exists.
- [ ] Public artifact is labeled reference code, not the private system or an external-client production proof.
