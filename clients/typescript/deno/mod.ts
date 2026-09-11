export interface ClientOptions {
  baseUrl: string;
  bearerToken?: string;
}

export class Client {
  readonly baseUrl: URL;
  readonly bearerToken?: string;

  constructor(options: ClientOptions) {
    const baseUrl = new URL(options.baseUrl);

    if (
      !["http:", "https:"].includes(baseUrl.protocol) ||
      baseUrl.username !== "" ||
      baseUrl.password !== "" ||
      baseUrl.search !== "" ||
      baseUrl.hash !== ""
    ) {
      throw new TypeError(
        "baseUrl must be a credential-free absolute HTTP(S) URL without a query or fragment",
      );
    }

    this.baseUrl = baseUrl;
    this.bearerToken = options.bearerToken;
  }

  toJSON(): { baseUrl: string } {
    return { baseUrl: this.baseUrl.toString() };
  }
}
