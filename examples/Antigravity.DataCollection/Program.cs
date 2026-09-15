using Antigravity.DataCollection;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Polly;
using Polly.Extensions.Http;

var builder = Host.CreateApplicationBuilder(args);
builder.Services.AddHttpClient("market")
    .AddPolicyHandler(HttpPolicyExtensions
        .HandleTransientHttpError()
        .Or<TaskCanceledException>()
        .WaitAndRetryAsync(3, attempt => TimeSpan.FromMilliseconds(250 * Math.Pow(2, attempt))));
builder.Services.AddSingleton<IQuoteConnector, NobitexConnector>();
builder.Services.AddHostedService<CollectionWorker>();

await builder.Build().RunAsync();
