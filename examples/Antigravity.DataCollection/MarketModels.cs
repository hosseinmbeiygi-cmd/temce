namespace Antigravity.DataCollection;

public enum AssetClass { GoldEtf, Gold, Fx, Crypto, Global, Commodity }
public enum QualityFlag { Clean, Suspicious, Stale, Invalid }

public sealed record CanonicalMarketTick(
    string Source,
    string Instrument,
    AssetClass AssetClass,
    DateTimeOffset ObservedAt,
    decimal Price,
    decimal? Bid = null,
    decimal? Ask = null,
    decimal? Volume = null,
    string Currency = "IRR",
    QualityFlag Quality = QualityFlag.Clean,
    IReadOnlyList<string>? QualityReasons = null);

public interface IQuoteConnector
{
    string Name { get; }
    Task<CanonicalMarketTick?> FetchAsync(CancellationToken cancellationToken);
}
