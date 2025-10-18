<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount, onDestroy } from 'svelte';

	let vantaEffect: any;

	// Hardcoded subreddits with descriptions
	const subreddits = [
		{
			name: 'news',
			display: 'r/news',
			description: 'Breaking news and current events from around the world.'
		},
		{
			name: 'unpopularopinion',
			display: 'r/unpopularopinion',
			description: 'Controversial takes and unconventional perspectives.'
		},
		{
			name: 'changemyview',
			display: 'r/changemyview',
			description: "Discussions aimed at changing people's minds."
		}
	];

	function selectSubreddit(subredditName: string) {
		goto(`/subreddit/${subredditName}`);
	}

	onMount(() => {
		// Initialize Vanta.js fog effect
		if (typeof window !== 'undefined' && (window as any).VANTA) {
			vantaEffect = (window as any).VANTA.FOG({
				el: "#vanta-bg",
				mouseControls: true,
				touchControls: true,
				gyroControls: false,
				minHeight: 200.00,
				minWidth: 200.00,
				highlightColor: 0x222222,
				midtoneColor: 0x101010,
				lowlightColor: 0x0,
				baseColor: 0x0,
				blurFactor: 0.45,
				zoom: 0.70
			});
		}
	});

	onDestroy(() => {
		if (vantaEffect) {
			vantaEffect.destroy();
		}
	});
</script>

<svelte:head>
	<title>Choose a Community - Reddit or Replicant</title>
	<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js"></script>
	<script src="https://cdn.jsdelivr.net/npm/vanta@latest/dist/vanta.fog.min.js"></script>
</svelte:head>

<!-- Vanta.js background -->
<div id="vanta-bg" class="fixed inset-0 w-full h-full" style="z-index: -1;"></div>

<div class="min-h-screen text-gray-100 relative z-10">
	<!-- Fixed Toolbar -->
	<div
		class="fixed top-0 left-0 right-0 z-50 border-b border-gray-700"
		style="background: rgba(17, 17, 20, 0.95); backdrop-filter: blur(10px);"
	>
		<div class="max-w-6xl mx-auto px-4 md:px-0 py-3">
			<div class="flex items-center justify-between">
				<a
					href="/"
					class="text-lg font-bold cursor-pointer hover:text-blue-300 transition-colors"
					style="color: #f3f4f6; text-shadow: 0 0 8px rgba(0, 212, 255, 0.1);"
				>
					Reddit or <span class="glitch" data-text="Replicant">Replicant</span>?
				</a>
				<div class="flex items-center gap-4">
					<a href="/about" class="transition-colors text-sm" style="color: #00d4ff;"> About </a>
				</div>
			</div>
		</div>
	</div>

	<!-- Content with top padding to account for fixed toolbar -->
	<div class="pt-16">
		<div class="container mx-auto p-8 md:px-0">
			<div class="max-w-6xl mx-auto">
				<!-- Header -->
				<div class="text-center mb-12">
					<!-- Tyrell Corporation Banner -->
					<div class="mb-16 mt-4">
						<h1
							class="text-3xl font-bold text-white mb-6"
							style="text-shadow: 0 0 15px rgba(255, 255, 255, 0.4), 0 0 30px rgba(173, 216, 230, 0.2);"
						>
							The Tyrell Corporation's infiltration has begun
						</h1>
						<p
							class="text-gray-300 text-lg max-w-4xl mx-auto leading-relaxed"
							style="text-shadow: 0 0 8px rgba(255, 255, 255, 0.1);"
						>
							Human-passing robots called <span
								class="font-bold text-red-500"
								style="text-shadow: 0 0 10px rgba(239, 68, 68, 0.8), 0 0 20px rgba(239, 68, 68, 0.6), 0 0 30px rgba(220, 38, 38, 0.4);"
								>Replicants</span
							> are now embedded within these communities
						</p>
					</div>
				</div>

				<!-- Subreddit Cards -->
				<div class="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
					{#each subreddits as subreddit}
						<div
							class="border border-gray-700 rounded-lg p-8 cursor-pointer transition-all duration-200 hover:border-blue-400 hover:scale-105"
							style="background: rgba(17, 17, 20, 0.85); backdrop-filter: blur(10px);"
							on:click={() => selectSubreddit(subreddit.name)}
							on:keydown={(e) => e.key === 'Enter' && selectSubreddit(subreddit.name)}
							role="button"
							tabindex="0"
						>
							<div class="text-center">
								<h3
									class="text-xl font-semibold mb-4"
									style="color: #00d4ff; text-shadow: 0 0 8px rgba(0, 212, 255, 0.2);"
								>
									{subreddit.display}
								</h3>
								<p class="text-gray-300 leading-relaxed content-text">
									{subreddit.description}
								</p>
								<div class="mt-6">
									<button
										class="px-6 py-2 text-white rounded transition-all duration-200 hover:scale-105 cursor-pointer"
										style="background: linear-gradient(135deg, var(--replicant-primary), var(--replicant-secondary)); border: 1px solid var(--replicant-border);"
										on:mouseenter={(e) =>
											(e.target.style.boxShadow = '0 0 15px var(--replicant-glow)')}
										on:mouseleave={(e) => (e.target.style.boxShadow = '')}
									>
										Enter Community
									</button>
								</div>
							</div>
						</div>
					{/each}
				</div>
			</div>
		</div>
	</div>
</div>
