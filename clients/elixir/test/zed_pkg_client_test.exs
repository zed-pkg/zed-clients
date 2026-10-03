defmodule ZedPkgClientTest do
  use ExUnit.Case, async: true

  test "rejects credentials in the registry URL" do
    assert_raise ArgumentError, fn -> ZedPkgClient.new(registry_url: "https://user:pass@example.com") end
  end

  test "accepts an absolute HTTP URL" do
    assert %ZedPkgClient{} = ZedPkgClient.new(registry_url: "http://localhost:8080/api/")
  end

  test "redacts bearer tokens from struct inspection" do
    secret = "den-3450-test-token"
    rendered = inspect(ZedPkgClient.new(token: secret))

    refute rendered =~ secret
    refute rendered =~ "token:"
    assert rendered =~ "ZedPkgClient"
  end
end
