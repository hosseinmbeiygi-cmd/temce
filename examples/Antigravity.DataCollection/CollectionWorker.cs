using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Antigravity.DataCollection;

public sealed class CollectionWorker(
    IQuoteConnector connector,
    ILogger<CollectionWorker> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(15));
        while (await timer.WaitForNextTickAsync(stoppingToken))
        {
            try
            {
                var tick = await connector.FetchAsync(stoppingToken);
                if (tick is not null)
                    logger.LogInformation("{Source} {Instrument}={Price} {ObservedAt:o}",
                        tick.Source, tick.Instrument, tick.Price, tick.ObservedAt);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { }
            catch (Exception exception)
            {
                logger.LogError(exception, "Collection failed for {Source}", connector.Name);
            }
        }
    }
}
