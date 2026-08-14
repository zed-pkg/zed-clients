import gleam/option.{type Option}
pub type Client { Client(base_url: String, bearer_token: Option(String)) }
pub fn new(base_url: String, bearer_token: Option(String)) -> Client { Client(base_url:, bearer_token:) }
pub fn health(client: Client) -> Bool { client.base_url != "" }
