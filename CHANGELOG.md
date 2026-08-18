# Changelog

<!-- version list -->

## v0.6.3 (2026-08-18)

### Bug Fixes

- **api**: Send numeric-only app version to OK
  ([#20](https://github.com/RaMin0/homeassistant-ok/pull/20),
  [`6b2193a`](https://github.com/RaMin0/homeassistant-ok/commit/6b2193aff32bbc8c26e4f81a1fa7cd3657d61331))

### Chores

- **deps**: Bump google-auth from 2.55.1 to 2.55.2
  ([#13](https://github.com/RaMin0/homeassistant-ok/pull/13),
  [`801c795`](https://github.com/RaMin0/homeassistant-ok/commit/801c795206269f669b27c35b7f66c0294cb31eb9))

- **deps**: Bump home-assistant/actions/hassfest from e3fb68ebda13d88a0d695082f471ba2c83d025fb to
  ab22029681aa532bfe7de5774a9972d67bfbd2c0 in the github-actions group
  ([#15](https://github.com/RaMin0/homeassistant-ok/pull/15),
  [`6759a15`](https://github.com/RaMin0/homeassistant-ok/commit/6759a159c1daec04f119f33c300f7cb08109774f))

- **deps**: Bump ruff from 0.16.0 to 0.16.1 in the python-dependencies group
  ([#14](https://github.com/RaMin0/homeassistant-ok/pull/14),
  [`541fb23`](https://github.com/RaMin0/homeassistant-ok/commit/541fb23a2d39b3bcace03d81772e5ab150c565a1))

- **deps**: Bump the github-actions group across 1 directory with 4 updates
  ([#10](https://github.com/RaMin0/homeassistant-ok/pull/10),
  [`d2222f1`](https://github.com/RaMin0/homeassistant-ok/commit/d2222f1a1b65fbd41f9ec68f71bd0d8fd8422dca))

- **deps-dev**: Bump python-semantic-release from 10.5.3 to 10.6.1 in the python-dependencies group
  across 1 directory ([#12](https://github.com/RaMin0/homeassistant-ok/pull/12),
  [`f0c842d`](https://github.com/RaMin0/homeassistant-ok/commit/f0c842de0165e02d6a12198439950c91537e0491))

### Continuous Integration

- Restore green validation pipeline ([#18](https://github.com/RaMin0/homeassistant-ok/pull/18),
  [`594c1f9`](https://github.com/RaMin0/homeassistant-ok/commit/594c1f9b4b29d9f913c452d14aff86b83aaa8129))


## v0.6.2 (2026-08-02)

### Bug Fixes

- **ci**: Make validation toolchain deterministic
  ([#11](https://github.com/RaMin0/homeassistant-ok/pull/11),
  [`5bf01f9`](https://github.com/RaMin0/homeassistant-ok/commit/5bf01f9bad3185afa4753af931cc3f3963f43b50))


## v0.6.1 (2026-07-06)

### Bug Fixes

- **deps**: Restore Home Assistant compatible Firestore pin
  ([`fb2a1ad`](https://github.com/RaMin0/homeassistant-ok/commit/fb2a1ad2b9719612aa3cf36e655248b7bbc0322a))

### Chores

- **deps**: Bump google-cloud-firestore from 2.27.0 to 2.28.0 in the python-dependencies group
  ([`f75c330`](https://github.com/RaMin0/homeassistant-ok/commit/f75c330e7c69a68ba1ea92e7a65afbe9e7591b46))


## v0.6.0 (2026-07-04)

### Continuous Integration

- Add release readiness validation
  ([`92e7485`](https://github.com/RaMin0/homeassistant-ok/commit/92e74850466e101ae0c74cf1e71a9f2f15ec6695))

### Documentation

- Expand public support guidance
  ([`6db9bfe`](https://github.com/RaMin0/homeassistant-ok/commit/6db9bfe21e37ef6fd20405498b5029e684ee596b))

### Features

- Expose realtime watcher health diagnostics
  ([`fe8f7b4`](https://github.com/RaMin0/homeassistant-ok/commit/fe8f7b43126b37579c18fd19afa99c59922fa71d))

### Testing

- Cover OK schedule and Firestore contracts
  ([`d55d6f9`](https://github.com/RaMin0/homeassistant-ok/commit/d55d6f9bda31e0c606fd8e274fb880f3fee7195e))


## v0.5.1 (2026-07-04)

### Bug Fixes

- Harden OK entity and device handling
  ([`165ca5c`](https://github.com/RaMin0/homeassistant-ok/commit/165ca5cdf2aff48a4eb07907e3b3529f65bf88ae))

- **api**: Harden OK client error handling
  ([`5cae71e`](https://github.com/RaMin0/homeassistant-ok/commit/5cae71e9a25b186fe45e500e942ce229d4a36332))

- **config-flow**: Classify OK validation failures
  ([`514801c`](https://github.com/RaMin0/homeassistant-ok/commit/514801c26c88338db5ef75f2106649000b17f627))

### Continuous Integration

- Validate HACS release artifacts
  ([`f7f1ba1`](https://github.com/RaMin0/homeassistant-ok/commit/f7f1ba1ae07d7bf9209c1c1260a9110c6d3c8faf))

### Testing

- Load device registry before entity registry
  ([`e3e2384`](https://github.com/RaMin0/homeassistant-ok/commit/e3e2384d6ed1379559a0d8c2be420504b372b426))


## v0.5.0 (2026-07-03)

### Continuous Integration

- Isolate Home Assistant validation tooling
  ([`727a442`](https://github.com/RaMin0/homeassistant-ok/commit/727a442a46802de44243f461bddc2d314274be98))

### Features

- Improve charger session and schedule state handling
  ([`24613a1`](https://github.com/RaMin0/homeassistant-ok/commit/24613a1db662b05174d63ad59c47944a768e5415))

### Testing

- Make schedule freshness test deterministic
  ([`1658159`](https://github.com/RaMin0/homeassistant-ok/commit/1658159c24fcc076fbd1c56ad50b390c844a44da))


## v0.4.3 (2026-07-02)

### Bug Fixes

- Preserve realtime schedule freshness
  ([`d88143c`](https://github.com/RaMin0/homeassistant-ok/commit/d88143cf1d57119911ce5ec52a456f63179c0abc))

- Stabilize charger schedule state
  ([`e6325fd`](https://github.com/RaMin0/homeassistant-ok/commit/e6325fd45b0cf4511c2adf43d08b49125aaec83d))

- **api**: Support current charging schedule payloads
  ([`5ae7b91`](https://github.com/RaMin0/homeassistant-ok/commit/5ae7b91b6d2b7ad0647314db89f296ec4e751de5))

### Documentation

- Document OK schedule behavior
  ([`f95be0c`](https://github.com/RaMin0/homeassistant-ok/commit/f95be0c27ae7f3728e33f8f1a86bb4ef359e9fdd))


## v0.4.2 (2026-07-01)

### Bug Fixes

- Handle OK current charging schedule changes
  ([`fcf1221`](https://github.com/RaMin0/homeassistant-ok/commit/fcf1221f00402864d99dce535f2e9b107777b853))

### Documentation

- Align release guidance
  ([`1521627`](https://github.com/RaMin0/homeassistant-ok/commit/1521627dd24424b5670b62d8d7ba0f2c31bc4c65))


## v0.4.1 (2026-06-29)

### Bug Fixes

- Declare config entry schema statically
  ([`40cf8fc`](https://github.com/RaMin0/homeassistant-ok/commit/40cf8fca006e0640223c67fb820718f7f14d5008))

### Chores

- **deps**: Bump google-auth from 2.55.0 to 2.55.1 in the python-dependencies group across 1
  directory ([#6](https://github.com/RaMin0/homeassistant-ok/pull/6),
  [`d2d78b5`](https://github.com/RaMin0/homeassistant-ok/commit/d2d78b540d9c508891d70e5b46a1f8cbb5297656))

- **deps**: Bump home-assistant/actions/hassfest from e91ad1948e57189485b9c1ad608af0c303946f89 to
  f4ca6f671bd429efb108c0f2fa0ae8af0215986c in the github-actions group across 1 directory
  ([#5](https://github.com/RaMin0/homeassistant-ok/pull/5),
  [`e6e5549`](https://github.com/RaMin0/homeassistant-ok/commit/e6e5549eeb8855290c549d41e7a3716449153d4a))

### Continuous Integration

- Cache Python dependencies in validation
  ([`f02ba35`](https://github.com/RaMin0/homeassistant-ok/commit/f02ba35c091bd4288d1f2c030caf09985eaebe04))

- Fix dependabot commit scope
  ([`f6b4ab2`](https://github.com/RaMin0/homeassistant-ok/commit/f6b4ab279cdc5595660d607fbe16b0662da48832))

- Reduce dependabot noise
  ([`a0e1d84`](https://github.com/RaMin0/homeassistant-ok/commit/a0e1d84633f743aac9f210f062fdaff4cfea4e53))

### Testing

- Isolate bundled API client imports
  ([`b46e227`](https://github.com/RaMin0/homeassistant-ok/commit/b46e227d3aa9b6f596e66bbfcc1a5fecb698a1fb))


## v0.4.0 (2026-06-29)

### Bug Fixes

- Harden OK entity availability and names
  ([`fff2b6b`](https://github.com/RaMin0/homeassistant-ok/commit/fff2b6b7e44154cc6c12af3caed8990dde1661e1))

### Continuous Integration

- Allow release workflow to push through ruleset
  ([`3d63854`](https://github.com/RaMin0/homeassistant-ok/commit/3d638544eff0e90142eeaa2fc6fad08beaadbd3b))

- Create release PR before publishing
  ([`63f47dd`](https://github.com/RaMin0/homeassistant-ok/commit/63f47ddc04104b47325d3536b055007a2ef00ba0))

- Guard workflow write permissions
  ([`bc476f7`](https://github.com/RaMin0/homeassistant-ok/commit/bc476f79668f28cee10d37c72510fd45489594aa))

- Run quality checks on hosted python
  ([`9d1fb9c`](https://github.com/RaMin0/homeassistant-ok/commit/9d1fb9ca002f471378f7e541ef2af1840444206f))

- Run ruff before editable install
  ([`14d05d9`](https://github.com/RaMin0/homeassistant-ok/commit/14d05d9b399964a6fcc902735f885776988e67b9))

- Split validation workflow jobs
  ([`d755457`](https://github.com/RaMin0/homeassistant-ok/commit/d755457c3d1ee5a3e6a3038e0ab6571b012ec457))

- Strengthen validation and package checks
  ([`78d0079`](https://github.com/RaMin0/homeassistant-ok/commit/78d007932c3ad1cb702fc74060f0d59cb9f911f3))

- Use release token for protected releases
  ([`e62959d`](https://github.com/RaMin0/homeassistant-ok/commit/e62959d60dc9b26468fccbea8ea24697df8249c8))

### Features

- Align OK actions with Home Assistant targets
  ([`26b42b2`](https://github.com/RaMin0/homeassistant-ok/commit/26b42b298f585a33124a9016202862e1e317cc97))

### Refactoring

- Split OK integration runtime module
  ([`ed940e3`](https://github.com/RaMin0/homeassistant-ok/commit/ed940e3ecbe7dee133dea0a21f39edfc3ecac8ee))


## v0.3.1 (2026-06-27)

### Bug Fixes

- Normalize quick receipt energy units
  ([`f08987a`](https://github.com/RaMin0/homeassistant-ok/commit/f08987a2f007b4eee354a7d1b67700a47b0945f9))

### Chores

- Keep private planning notes local
  ([`85ae701`](https://github.com/RaMin0/homeassistant-ok/commit/85ae70198c4f9c30db46b309c0121588a1e47932))

- **github**: Improve issue triage metadata
  ([`9ecfe10`](https://github.com/RaMin0/homeassistant-ok/commit/9ecfe10d40163660c7fb1c82b5f804d100d595d5))

### Continuous Integration

- Release without protected branch pushes
  ([`57a0ca9`](https://github.com/RaMin0/homeassistant-ok/commit/57a0ca9a112c5fc807cdc27c9d3f3384222fb511))

- Remove release token fallback
  ([`dd9e28c`](https://github.com/RaMin0/homeassistant-ok/commit/dd9e28c3049b01e7fac23a299c2057068a7702d8))

- Skip stale release workflow runs
  ([`95f7095`](https://github.com/RaMin0/homeassistant-ok/commit/95f709522f48f9d617bf067eb4171a90fb2b0a4f))

### Documentation

- Add Danish README
  ([`8936535`](https://github.com/RaMin0/homeassistant-ok/commit/89365350e6eec3666b0e03dfb676ca5d96634830))

- Add usage screenshots and realtime notes
  ([`f610cd7`](https://github.com/RaMin0/homeassistant-ok/commit/f610cd7a0eaa0099be4cb2754a21d5941a2df748))

- Align maintainer release guidance
  ([`7574070`](https://github.com/RaMin0/homeassistant-ok/commit/7574070c7428c024f3373873b72f60de8ea337c1))

- Align publishing and repository guidance
  ([`6d8b747`](https://github.com/RaMin0/homeassistant-ok/commit/6d8b7476831bcdac221b88df4b7792957d0d0d67))

- Clarify public usage documentation
  ([`5e07ed0`](https://github.com/RaMin0/homeassistant-ok/commit/5e07ed026e5b63b80671e49ca8ed2b1fd700bd88))

- Update usage examples and behavior docs
  ([`a323588`](https://github.com/RaMin0/homeassistant-ok/commit/a323588fbc3ea837d0a9895f9f6d12fb408bebe1))


## v0.3.0 (2026-06-21)

### Bug Fixes

- **ci**: Restore release version commits
  ([`6cff8e3`](https://github.com/RaMin0/homeassistant-ok/commit/6cff8e3c7f9bb273444edf7d82ee071041ea818f))

### Continuous Integration

- Upload hacs asset during semantic release
  ([`fd7a879`](https://github.com/RaMin0/homeassistant-ok/commit/fd7a879201261379ddf034b680e052829dc5c26e))


## v0.2.0 (2026-06-20)

### Bug Fixes

- Keep dependency validation in sync
  ([`73be29a`](https://github.com/RaMin0/homeassistant-ok/commit/73be29ad8f18a76a0a4fab8095fe761a3e85f621))

### Continuous Integration

- Bump checkout action to v7
  ([`d095531`](https://github.com/RaMin0/homeassistant-ok/commit/d095531a83613a7c15f506becc9b08d372aa0dc5))

### Features

- Improve update options and release readiness
  ([`0f8713d`](https://github.com/RaMin0/homeassistant-ok/commit/0f8713d598259e04b3d9c0508ace972421d44f83))


## v0.1.2 (2026-06-20)

### Bug Fixes

- Use uniform entity id suggestions
  ([`24cf754`](https://github.com/RaMin0/homeassistant-ok/commit/24cf754b9a20d4837fbd9eacbfc07b13bd3032a4))


## v0.1.1 (2026-06-20)

### Bug Fixes

- Correct GitHub owner casing
  ([`1f5da74`](https://github.com/RaMin0/homeassistant-ok/commit/1f5da7477b573d3fb21da184c50b6da44119414d))

- Refine charger registry and blueprint defaults
  ([`6705dd4`](https://github.com/RaMin0/homeassistant-ok/commit/6705dd493949e4563b1c0cd098fc01c5337170c5))


## 0.1.0

- Initial public OK Home Assistant custom integration.
- Bundled OK API client.
- Config flow, reauth, options, diagnostics, services, sensors, switches, buttons, and
  Firestore realtime watcher support.
- Raise typed OK command errors for application-level command failures.
- Validate core API response shapes before returning typed client models.
- Pass configured timeouts to injected sync and async HTTP transports.
- Remove current config-entry persistence of login tokens and clean up legacy entries.
- Harden Firestore realtime watcher queue handling and document anonymous watcher credentials.
