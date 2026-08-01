/**
 * Popup Manager – Editor-Formular
 *
 * Blendet die Felder ein, die zur jeweiligen Auswahl gehören.
 */
( function () {
	'use strict';

	/**
	 * Sichtbarkeit anhand eines Attributwerts umschalten.
	 *
	 * @param {string} attribute Data-Attribut der Zielelemente.
	 * @param {string} value     Aktuell ausgewählter Wert.
	 * @return {void}
	 */
	function toggle( attribute, value ) {
		var targets = document.querySelectorAll( '[' + attribute + ']' );

		Array.prototype.forEach.call( targets, function ( el ) {
			el.classList.toggle( 'is-visible', el.getAttribute( attribute ) === value );
		} );
	}

	/**
	 * Aktuell gewählte Platzierung.
	 *
	 * @return {string} Wert des aktiven Radiobuttons.
	 */
	function selectedWhere() {
		var checked = document.querySelector( '[data-pm-where]:checked' );

		return checked ? checked.value : 'all';
	}

	/**
	 * WordPress-Farbwähler aktivieren. Ohne jQuery bleibt das Textfeld
	 * bestehen, in das sich der Hex-Wert direkt eintragen lässt.
	 *
	 * @return {void}
	 */
	function initColorPickers() {
		var $ = window.jQuery;

		if ( ! $ || ! $.fn || ! $.fn.wpColorPicker ) {
			return;
		}

		$( '.pm-color' ).wpColorPicker();
	}

	/**
	 * Prozentwert neben dem Schieberegler mitführen.
	 *
	 * @return {void}
	 */
	function initOpacity() {
		var slider = document.querySelector( '[data-pm-opacity]' );
		var output = document.querySelector( '[data-pm-opacity-value]' );

		if ( ! slider || ! output ) {
			return;
		}

		slider.addEventListener( 'input', function () {
			output.textContent = slider.value + ' %';
		} );
	}

	document.addEventListener( 'DOMContentLoaded', function () {
		var whereInputs = document.querySelectorAll( '[data-pm-where]' );
		var frequency = document.querySelector( '[data-pm-frequency]' );

		initColorPickers();
		initOpacity();

		if ( ! whereInputs.length && ! frequency ) {
			return;
		}

		Array.prototype.forEach.call( whereInputs, function ( input ) {
			input.addEventListener( 'change', function () {
				toggle( 'data-pm-when', selectedWhere() );
			} );
		} );

		if ( frequency ) {
			frequency.addEventListener( 'change', function () {
				toggle( 'data-pm-when-frequency', frequency.value );
			} );
		}

		toggle( 'data-pm-when', selectedWhere() );

		if ( frequency ) {
			toggle( 'data-pm-when-frequency', frequency.value );
		}
	} );
}() );
