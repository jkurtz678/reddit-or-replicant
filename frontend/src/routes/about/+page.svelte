<script lang="ts">
	import { onMount } from 'svelte';
	import { fade } from 'svelte/transition';

	let contentVisible = false;

	onMount(() => {
		// Trigger fade-in animation
		setTimeout(() => {
			contentVisible = true;
		}, 100);
	});
</script>

<svelte:head>
	<title>About - Reddit or Replicant</title>
</svelte:head>

<div class="min-h-screen text-gray-100 relative z-10">
	<!-- Fixed Toolbar -->
	<div class="fixed top-0 left-0 right-0 z-50 border-b border-gray-700" style="background: rgba(17, 17, 20, 0.95); backdrop-filter: blur(10px);">
		<div class="max-w-4xl mx-auto px-4 md:px-0 py-3">
			<div class="flex items-center justify-between">
				<a href="/" class="text-lg font-bold cursor-pointer hover:text-blue-300 transition-colors" style="color: #f3f4f6; text-shadow: 0 0 8px rgba(0, 212, 255, 0.1);">
					Reddit or <span class="glitch" data-text="Replicant">Replicant</span>?
				</a>
				<div class="flex items-center gap-4">
					<a href="/subreddit" class="transition-colors text-sm" style="color: #00d4ff;" >
						Play Game
					</a>
				</div>
			</div>
		</div>
	</div>

	<!-- Content with top padding to account for fixed toolbar -->
	<div class="pt-16">
		{#if contentVisible}
		<div class="max-w-4xl mx-auto px-4 md:px-0 py-12" transition:fade={{ duration: 1000 }}>
			<div class="max-w-3xl mx-auto">
				<h1 class="text-4xl font-bold mb-8 text-center" style="color: #f3f4f6; text-shadow: 0 0 12px rgba(0, 212, 255, 0.1);">
					About Reddit or <span class="glitch" data-text="Replicant">Replicant</span>
				</h1>

				<div class="space-y-8 text-gray-200 text-lg leading-relaxed content-text">
					<p>
						<a href="https://www.sciencedirect.com/science/article/pii/S2451958824001714" class="underline transition-colors" style="color: #00d4ff;" target="_blank" rel="noopener noreferrer">Recent</a> <a href="https://www.nature.com/articles/s41598-024-76218-y" class="underline transition-colors" style="color: #00d4ff;" target="_blank" rel="noopener noreferrer">studies</a> show that humans can barely distinguish social media content created by the latest AI generated models from real human-created content. The accessibility of this technology enables malicious actors to perform large-scale online manipulation. The platforms that dominate the internet refuse to adopt identity verification or other anti-bot countermeasures and instead continuously prioritize profits over protecting their users.
					</p>

					<p>
						The true scale of this problem is hard to measure, but documented evidence reveals it is already widespread:
					</p>

					<ul class="space-y-4 ml-6 list-disc">
						<li>Russian-sponsored disinformation campaigns <a href="https://academic.oup.com/pnasnexus/article/4/4/pgaf083/8097936" class="underline transition-colors" style="color: #00d4ff;" target="_blank" rel="noopener noreferrer">are now using generative AI</a> to increase their content production while maintaining equal levels of persuasiveness</li>
						<li>The Chinese government <a href="https://www.npr.org/2024/09/03/nx-s1-5096151/china-tiktok-x-fake-voters-influence-campaign" class="underline transition-colors" style="color: #00d4ff;" target="_blank" rel="noopener noreferrer">created thousands of AI-generated accounts</a> posing as American voters in order to escalate tensions before the 2024 election</li>
						<li>University of Zurich researchers <a href="https://www.nbcnews.com/tech/tech-news/reddiit-researchers-ai-bots-rcna203597" class="underline transition-colors" style="color: #00d4ff;" target="_blank" rel="noopener noreferrer">deployed AI bots</a> that successfully posted over 1,000 manipulative comments on Reddit, with the AI content proving 3-6 times more persuasive than human posts while remaining undetected by users</li>
						<li>University of Notre Dame researchers <a href="https://news.nd.edu/news/social-media-platforms-arent-doing-enough-to-stop-harmful-ai-bots-research-finds/" class="underline transition-colors" style="color: #00d4ff;" target="_blank" rel="noopener noreferrer">found that Reddit's AI bot detection systems are "trivial" to bypass</a>, with test bots successfully posting content on the platform despite stated policies against automated accounts</li>
					</ul>

					<p>
						Reddit or Replicant demonstrates how difficult it is to tell what is real on the modern internet. What looks like genuine human discourse can no longer be trusted until platforms adopt new policies for verifying user identities and blocking AI generated content. To learn more and get involved in advancing bipartisan policy solutions to combat AI-generated misinformation, visit the <a href="https://bipartisanpolicy.org/project/artificial-intelligence/" class="underline transition-colors" style="color: #00d4ff;" target="_blank" rel="noopener noreferrer">Bipartisan Policy Center's AI research</a> and <a href="https://bipartisanpolicy.org/donation-impact/" class="underline transition-colors" style="color: #00d4ff;" target="_blank" rel="noopener noreferrer">support their advocacy work</a> for evidence-based regulations that can restore trust in our digital information environment.
					</p>

					<!-- <p class="text-center pt-8">
						<a 
							href="/subreddit" 
							class="px-8 py-4 text-white text-xl rounded transition-all duration-200 cursor-pointer hover:scale-105 font-semibold inline-block"
							style="background: linear-gradient(135deg, var(--replicant-dark), var(--replicant-light)); border: 1px solid var(--replicant-border); box-shadow: 0 4px 15px var(--replicant-shadow);"
							on:mouseenter={(e) => e.target.style.boxShadow = '0 6px 25px var(--replicant-glow)'}
							on:mouseleave={(e) => e.target.style.boxShadow = '0 4px 15px var(--replicant-shadow)'}
						>
							Test Your Detection Skills
						</a>
					</p> -->
				</div>
			</div>
		</div>
		{/if}
	</div>
</div>