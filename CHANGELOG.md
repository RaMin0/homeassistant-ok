# Changelog

<!-- version list -->

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
