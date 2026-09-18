import test from "node:test";
import assert from "node:assert/strict";
import {
  artifactPath,
  filePath,
  packagePath,
  versionPath,
  yankPath,
} from "../dist/index.js";
import { Routes } from "../dist/generated/zed-api.routes.js";

test("generated route map matches TypeScript path helpers", () => {
  const org = "acme";
  const name = "kit";
  const version = "1.2.0";
  const sha = "abc123";
  assert.equal(Routes.get_package.buildPath({ org, name }), packagePath(org, name));
  assert.equal(Routes.get_version.buildPath({ org, name, version }), versionPath(org, name, version));
  assert.equal(Routes.get_artifact.buildPath({ sha256: sha }), artifactPath(sha));
  assert.equal(Routes.yank.buildPath({ org, name, version }), yankPath(org, name, version));
  assert.equal(
    Routes.get_file.buildPath({ org, name, version, path: "style.css" }),
    filePath(org, name, version, "style.css"),
  );
  assert.deepEqual([...Routes.get_version.transports], ["http", "tcp"]);
  assert.deepEqual([...Routes.registry_events.transports], ["websocket"]);
  assert.equal(Routes.cdn_content_object.path, "/artifacts/{sha256}.{ext}");
  assert.equal(
    Routes.cdn_package_object.buildPath({
      org,
      name,
      version,
      filename: `${name}-${version}.tar.gz`,
    }),
    `/packages/${org}/${name}/${version}/${name}-${version}.tar.gz`,
  );
});
