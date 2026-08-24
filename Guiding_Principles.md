# Guiding Principles

## Overall Intent

In cyber work, the manual often does not exist. You will not be given "click this, click that" guides. You will be given a mission objective, constraints, and an operational "why." Figuring out the "how" — and troubleshooting when it inevitably breaks — is the core of the job.

To succeed in this pipeline and your future roles, you must adhere to the following principles.

## Who This Is For

You are not being trained to become an operator. You are being trained to *understand the terrain* well enough to analyze it, characterize it, and report on it with authority. That requires building the same infrastructure the target runs: domains, DNS, certificates, tunnels, cloud services, and the telemetry that watches all of it.

You cannot credibly assess a network you have never stood up. Every task in this pipeline exists because analytic judgment about a system degrades quickly when it is not grounded in hands-on familiarity with how that system actually behaves.

## The Principles

### 1. The AI Policy: "Embrace, but Defend"

You are fully authorized and encouraged to use Artificial Intelligence to generate boilerplate code, troubleshoot errors, and explain complex concepts. However, AI is a tutor, not a crutch.

**The Standard — "Defend Your Code":** Instructors will point to random lines of your scripts, subnet masks, or configuration flags. You must be able to explain exactly what that line is doing. If an AI "barfs out" a script for you and you cannot explain how it works under the hood, the task is marked incomplete.

**A note on what these tasks deliberately withhold:** You will notice the tasks name the tool and the end state but rarely the exact command, flag, or cmdlet. That is not an oversight, and it is not us being coy — finding the command *is* the task. Asking an AI "how does a package manager resolve a package ID?" or "what is this configuration file actually controlling?" is using it as a tutor. Asking it to hand you the exact command for the task in front of you is skipping the repetition that builds the recall you'll need when there's no AI in the loop.

### 2. CLI-First: Command Line & Automation Over GUIs

**The Standard:** Whenever possible, all setup steps, configurations, and build logs must be executed via the Command Line Interface (CLI) or through scripting.

**The Why:**

- **Operational Reality:** This work lives in the command line. Target systems rarely have GUIs, and pushing heavy graphical data over covert, low-bandwidth tunnels is loud and slow.
- **Repeatability:** Scripts and CLI commands can be version-controlled, audited, and perfectly repeated by a teammate.
- **Predictability:** GUIs constantly change with software updates and hide the underlying mechanics. CLI tools interact directly with the system's APIs, providing raw, predictable, and unfiltered control over the environment.

### 3. "Docs as Code" (Reproducibility)

In cyber operations, poor documentation is an operational liability. Your GitHub repository is your weapon system's maintenance log.

**The Standard:** If a teammate cannot clone your repository and entirely rebuild your environment by copying/pasting your CLI commands and scripts — without asking you a single question — your task is incomplete.

### 4. Embrace the Struggle

You are going to break things. You will spend hours trying to figure out why a machine won't ping, only to realize you missed a single character in a subnet mask. This is not a failure; this is the job. Learn to read error logs, research documentation, and isolate variables.

### 5. Snapshot Discipline (Cheap Insurance)

Snapshots cost you thirty seconds and disk space. A broken environment with no snapshot costs you a day. Before any change that touches firewall rules, GPOs, PKI configuration, or partition tables, **snapshot first.**

This isn't about avoiding the struggle — some tasks will break your environment deliberately, and recovering from those is the lesson. It's about making sure the struggle you're having is the one that was intended, not an unrelated cascading failure eating the time you needed for the actual lesson. Document your snapshot points in your Known Issues / Troubleshooting log as you go: what you were about to change, and what state you rolled back to when it went sideways.
