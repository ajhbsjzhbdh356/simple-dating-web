// static/script.js

document.addEventListener("DOMContentLoaded", function () {
	// Select all user cards that need to be animated
	const animatedCards = document.querySelectorAll(".user-card");

	// If there are no cards on the page, don't run the rest of the code
	if (animatedCards.length === 0) return;

	// Set up the Intersection Observer
	const observer = new IntersectionObserver(
		(entries) => {
			entries.forEach((entry) => {
				// If the card is in the viewport (on screen)
				if (entry.isIntersecting) {
					// Add the 'is-visible' class to trigger the CSS animation
					entry.target.classList.add("is-visible");
					// Stop observing this card once it's visible
					observer.unobserve(entry.target);
				}
			});
		},
		{
			// Options for the observer
			threshold: 0.1, // Trigger when 10% of the card is visible
		}
	);

	// Tell the observer to watch each of the cards
	animatedCards.forEach((card) => {
		observer.observe(card);
	});
});
