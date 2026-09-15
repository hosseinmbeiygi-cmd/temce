using System.Globalization;
using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.Extensions.Logging;

namespace Antigravity.DataCollection;

public sealed class NobitexConnector(IHttpClientFactory clients, ILogger<NobitexConnector> log) : IQuoteConnector
{
    public string Name => "nobitex_usdt";

    public async Task<CanonicalMarketTick?> FetchAsync(CancellationToken cancellationToken)
    {
        using var response = await clients.CreateClient("market")
            .GetAsync("https://api.nobitex.ir/v2/orderbook/USDTIRT", cancellationToken);
        response.EnsureSuccessStatusCode();
        using var document = JsonDocument.Parse(await response.Content.ReadAsStringAsync(cancellationToken));
        var root = document.RootElement.TryGetProperty("data", out var data) ? data : document.RootElement;
        var bid = Level(root, "bids");
        var ask = Level(root, "asks");
        var price = Number(root, "lastTradePrice") ?? (bid.HasValue && ask.HasValue ? (bid + ask) / 2 : bid ?? ask);
        if (!price.HasValue || price <= 0)
        {
            log.LogWarning("No valid price returned by {Source}", Name);
            return null;
        }
        return new CanonicalMarketTick(Name, "USDTIRT", AssetClass.Crypto,
            DateTimeOffset.UtcNow, price.Value, bid, ask);
    }

    private static decimal? Level(JsonElement root, string property)
    {
        if (!root.TryGetProperty(property, out var levels) || levels.GetArrayLength() == 0) return null;
        var first = levels[0];
        return first.ValueKind == JsonValueKind.Array ? Decimal(first[0]) :
            first.TryGetProperty("price", out var p) ? Decimal(p) : null;
    }

    private static decimal? Number(JsonElement root, string property) =>
        root.TryGetProperty(property, out var value) ? Decimal(value) : null;

    private static decimal? Decimal(JsonElement value) =>
        value.ValueKind == JsonValueKind.Number && value.TryGetDecimal(out var n) ? n :
        value.ValueKind == JsonValueKind.String &&
        decimal.TryParse(value.GetString(), NumberStyles.Any, CultureInfo.InvariantCulture, out var parsed)
            ? parsed : null;
}
