# Docker Image Types (Vendor Profiles) — Roadmap

Status: **proposal, not implemented**. This is the agreed direction for the
next iteration of vendor Docker support. Four vendor profiles already
exist across branches and prototypes — iol-runner (this branch), XRd and
the SR Linux prototype (vendor/skip-init family), and the FRR registry
appliance — enough evidence to justify the registry. Implement it as a
follow-up to the current PR series, shaped by all four rather than by
iol-runner alone.

## Problem

All Docker nodes share one template type (`template_type: "docker"`) and
one template schema. Vendor images (iol-runner, SR Linux, XRd, …) are
selected and configured today through **environment markers** — free-form
strings parsed by the compute (`GNS3_IOL_RUNNER`, `GNS3_IOL_MEMORY`,
`GNS3_IOL_STARTUP_CONFIG`, `GNS3_SKIP_INIT`, `GNS3_UNIX_SOCKET_NIO`, …).
Three pains have already surfaced:

1. **Invisible and unvalidated.** The markers do not exist in the API
   schema: no OpenAPI documentation, no validation, typo or bad value
   silently falls back to a default (`GNS3_IOL_MEMORY=notanumber` → 2048).
2. **The shared-schema dilemma.** Adding a vendor-specific field to the
   Docker template schema pollutes every Docker template with a field only
   one vendor reads; not adding it pushes everything into environment
   strings. The `startup_config` discussion (ended in the
   `GNS3_IOL_STARTUP_CONFIG` knob) is the canonical example — the tension
   exists because there is no legitimate discriminator dimension.
3. **Generic-feature applicability is implicit.** Which generic Docker
   features apply to which image is only documented in code comments:
   `mac_address` is meaningless under unix-socket NIO, `/etc/network`
   seeding is dead weight for skip-init images, `extra_configs` targets
   under persisted volumes get a (correct-but-noisy) shadow warning.

## Non-goal: new node types

A `template_type`/`node_type` per vendor (`"iol"`, `"srlinux"`, …) is
explicitly rejected. `node_type` is a top-level concept: it drives compute
module routing (`/projects/{id}/{node_type}/nodes`), capability
reporting, GUI node types and link handling. N vendor types that are all
Docker underneath would multiply routing and schema surface for zero
mechanism — vendor images are *content*, not mechanism, and GNS3's
appliance/template system is where content belongs.

## Design

### One discriminator field on Docker templates

```json
{
    "template_type": "docker",
    "image_type": "iol-runner",
    "image": "iol-xe/iol-xe:17-18-02"
}
```

`image_type` is optional; absent (or `"generic"`) keeps today's plain
`DockerVM` behavior and marker sniffing. The profiles that exist today,
mapped to their current mechanisms and archetypes:

| Profile | Current mechanism | Archetype |
|---|---|---|
| FRR appliance | plain `DockerVM`: init.sh `/etc/network` + `start_command` (frrinit.sh), console on PID 1 | generic |
| XRd | `VendorDockerVM` skip-init + `GNS3_SHM_SIZE`/`GNS3_DEVICES`, `extra_configs`, udev masking | vendor skip-init |
| SR Linux (prototype) | `VendorDockerVM` skip-init + `docker_exec` console + `GNS3_INTERFACE_NAMES` | vendor skip-init |
| iol-runner | `IOLDockerVM`: unix-socket NIO, per-start config generation, NVRAM startup-config | iol-runner |

Possible first values: `generic`, `iol-runner`, and a value for the
skip-init vendor NOS family once its common shape settles (XRd and SR
Linux may end up sharing it or splitting — that is exactly what the
registry should decide with all four in front of us).

### A compute-side registry

```python
IMAGE_PROFILES = {
    "iol-runner": {
        "class": IOLDockerVM,
        "fields": ("iol_memory", "startup_config"),   # schema-gated
        "capabilities": {...},                          # see below
    },
    ...
}
```

* **Class selection** moves from environment sniffing
  (`Docker._select_node_class`) to the field, with the existing markers
  kept as a fallback for templates created before the field existed
  (zero-migration compatibility).
* **Vendor parameters graduate into schema fields**, gated by pydantic
  conditional validation (accepted — and validated — only when
  `image_type` matches). This resolves the shared-schema dilemma properly:
  the field exists, but only means something for its profile. The
  environment knobs remain as the wire-level compatibility entry.
* **Capability declaration** makes generic-feature applicability data
  instead of comments:

  | Capability | plain Docker | vendor skip-init | iol-runner |
  |---|---|---|---|
  | `mac_address` honored | yes | yes | **no** (IOL derives MACs from the app id) |
  | `/etc/network` seeding | yes | no | no |
  | `extra_configs` targets under volumes | shadowed | works (real-path binds) | works |
  | console | telnet/http/… | `docker_exec` | PID 1 stdio (telnet) |
  | startup config | `extra_configs` injection | image-specific | nvram build (`nvram_import`) |

  Consumers: error/warning quality (don't warn about inapplicable
  features), the WebUI (vendor-aware template forms — a bonus, not a
  driver), and documentation generation.

The existing class hierarchy (`DockerVM` → `VendorDockerVM` →
`IOLDockerVM`) is unchanged — the registry only externalizes selection
and declaration.

## Migration & compatibility

* Old templates (markers only) keep working via the fallback; a one-time
  optional converter can rewrite markers → `image_type` + fields.
* The controller-side materialization conventions
  (`GNS3_IOL_STARTUP_CONFIG` file → `startup_config_content`, sent once)
  carry over unchanged — the field version references the same content
  pipeline.

## Roadmap steps

1. Add `image_type` to the Docker template schema (+ DB column +
   Alembic migration — see the three-place rule for template fields) and
   wire class selection through the registry, markers as fallback.
2. Move iol-runner knobs to gated fields (`iol_memory`,
   `startup_config`), deprecating-but-supporting the env forms.
3. Introduce the capability table and use it to silence inapplicable
   warnings (`mac_address`, `/etc/network`, extra-config shadowing).
4. Revisit per-vendor *schemas* (a sub-model per profile) only if a
   profile grows more than a handful of fields — not before.

## Open questions

* Field name: `image_type` vs `vendor` vs `runner` — decide when the
  second profile lands; the value vocabulary should name the *runtime
  contract*, not the vendor.
* Should appliances (`.gns3a`) carry `image_type` explicitly, or should
  installation keep deriving it from the appliance's environment block?
* Where the gated vendor fields live long-term: flat on the Docker
  template (simple, gated) vs nested `{"image_type": ..., "settings":
  {...}}` (cleaner, more schema churn).
