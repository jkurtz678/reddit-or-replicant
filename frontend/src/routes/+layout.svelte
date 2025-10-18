<script lang="ts">
	import "../app.css";
	import favicon from '$lib/assets/favicon.svg';
	import { onNavigate } from '$app/navigation';
	import { onMount, onDestroy } from 'svelte';

	let { children } = $props();
	let vantaEffect: any;

	// Add smooth page transitions using View Transition API
	onNavigate((navigation) => {
		if (!document.startViewTransition) return;

		return new Promise((resolve) => {
			document.startViewTransition(async () => {
				resolve();
				await navigation.complete;
			});
		});
	});

	onMount(() => {
		// Initialize Vanta.js fog effect once for all pages
		if (typeof window !== 'undefined' && (window as any).VANTA) {
			vantaEffect = (window as any).VANTA.FOG({
				el: "#vanta-bg",
				mouseControls: true,
				touchControls: true,
				gyroControls: false,
				minHeight: 200.00,
				minWidth: 200.00,
				highlightColor: 0x2a3340,  // More subtle blue-gray (15% darker)
				midtoneColor: 0x141a23,    // Darker blue-gray
				lowlightColor: 0x080b10,   // Very dark blue-black
				baseColor: 0x000000,       // Pure black base
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
	<link rel="icon" href={favicon} />
	<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js"></script>
	<script src="https://cdn.jsdelivr.net/npm/vanta@latest/dist/vanta.fog.min.js"></script>
</svelte:head>

<!-- Vanta.js background (persists across all pages) -->
<div id="vanta-bg" class="fixed inset-0 w-full h-full" style="z-index: -1;"></div>

{@render children?.()}
