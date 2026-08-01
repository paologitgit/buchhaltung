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

	document.addEventListener( 'DOMContentLoaded', function () {
		var whereInputs = document.querySelectorAll( '[data-pm-where]' );
		var frequency = document.querySelector( '[data-pm-frequency]' );

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
