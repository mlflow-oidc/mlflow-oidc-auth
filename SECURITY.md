# Security Policy

This project and its community take security bugs seriously. We appreciate efforts to improve the security of this software and follow the [GitHub coordinated disclosure of security vulnerabilities](https://docs.github.com/en/code-security/security-advisories/about-coordinated-disclosure-of-security-vulnerabilities#about-reporting-and-disclosing-vulnerabilities-in-projects-on-github) for responsible disclosure and prompt mitigation. We are committed to working with security researchers to resolve the vulnerabilities they discover.

## Supported Versions

The latest version of this project has continued support. If a critical vulnerability is found in the current version,
we may opt to backport patches to previous versions.

## Reporting a Vulnerability

When you find a security vulnerability in this project, please perform the following actions:

- [Open an issue](https://github.com/mlflow-oidc/mlflow-oidc-auth/issues/new?assignees=&labels=bug&template=bug_report_template.md&title=%5BBUG%5D%20Security%20Vulnerability) on the repository. Ensure that you use `[BUG] Security Vulnerability` as the title and _do not_ mention any vulnerability details in the issue post.
- Send a notification [email](mailto:opensource-security@kharkevich.com) to `opensource-security@kharkevich.com` that contains, at a minimum:
  - The link to the filed issue stub
  - Your GitHub handle
  - Detailed information about the security vulnerability, evidence that supports the relevance of the finding, and any reproducibility instructions for independent confirmation

This initial reporting stage ensures that rapid validation can occur without wasting the time and effort of the reporter. Future communication and vulnerability resolution will be conducted after validating the veracity of the reported issue.

A project maintainer will, after validating the report:

- Mark the issue as `priority/critical-urgent`
- Open a draft [GitHub Security Advisory](https://docs.github.com/en/code-security/security-advisories/creating-a-security-advisory) to discuss the vulnerability details in private

The private Security Advisory will be used to confirm the issue, prepare a fix, and publicly disclose it after the fix has been released.
