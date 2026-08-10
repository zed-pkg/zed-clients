import { Client } from "./mod.ts";

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) {
    throw new Error(message);
  }
}

Deno.test("constructs a client for a credential-free HTTPS registry", () => {
  const client = new Client({
    baseUrl: "https://registry.zpkg.tech/v1/",
    bearerToken: "den-3450-test-token",
  });

  assert(
    client.baseUrl.toString() === "https://registry.zpkg.tech/v1/",
    "the normalized base URL should be preserved",
  );
  assert(
    client.bearerToken === "den-3450-test-token",
    "the bearer token should remain available to request code",
  );
});

Deno.test("rejects credential-bearing and non-HTTP registry URLs", () => {
  for (const baseUrl of [
    "https://user:pass@registry.zpkg.tech",
    "file:///tmp/registry",
    "https://registry.zpkg.tech?token=secret",
    "https://registry.zpkg.tech#secret",
  ]) {
    let rejected = false;

    try {
      new Client({ baseUrl });
    } catch (error) {
      rejected = error instanceof TypeError;
    }

    assert(rejected, `expected ${baseUrl} to be rejected`);
  }
});

Deno.test("redacts bearer tokens from JSON serialization", () => {
  const secret = "den-3450-json-secret";
  const serialized = JSON.stringify(
    new Client({ baseUrl: "https://registry.zpkg.tech", bearerToken: secret }),
  );

  assert(!serialized.includes(secret), "serialized clients must not contain bearer tokens");
  assert(!serialized.includes("bearerToken"), "serialized clients must omit the bearer-token field");
  assert(serialized.includes("https://registry.zpkg.tech/"), "serialized clients should retain the registry URL");
});
