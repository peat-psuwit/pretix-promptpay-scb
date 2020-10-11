(function () {
    const stateUrl = $('#promptpay_scb_container').data('state-url');
    // Prevent double requests if the request takes a long time.
    let requestInFlight = false;

    const intervalId = setInterval(async () => {
        if (requestInFlight)
            return;

        requestInFlight = true;

        try {
            const response = await fetch(stateUrl);
            const state = await response.json();

            if (state.state == 'pending') {
                requestInFlight = false;
                return;
            } else if (state.state == 'confirmed' &&
                    typeof state.redirectTo === 'string') {
                window.location.replace(state.redirectTo);
            } else {
                // Our view should know better
                window.location.reload();
            }
        } catch (e) {
            console.error(e);
            requestInFlight = false;
        }
    }, 5000 /* msec = 5 sec */);
} ()); // Immediately Invoked Function Expressions