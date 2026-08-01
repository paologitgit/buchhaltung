/**
 * Popup Manager – Frontend
 *
 * Öffnet die Popups nach der eingestellten Verzögerung, merkt sich die
 * Anzeige im Browser und schliesst per Button, Hintergrundklick, Escape
 * oder Zeitablauf.
 */
( function () {
	'use strict';

	var data = window.popupManagerData || {};
	var configs = data.popups || [];
	var isPreview = !! data.isPreview;

	var current = null;
	var queue = [];
	var lastFocus = null;

	var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

	/**
	 * Schlüssel im Browserspeicher.
	 *
	 * @param {number} id Popup-ID.
	 * @return {string} Speicherschlüssel.
	 */
	function storageKey( id ) {
		return 'pm_popup_' + id;
	}

	/**
	 * Wurde das Popup laut Häufigkeitseinstellung bereits gezeigt?
	 *
	 * @param {Object} cfg Popup-Konfiguration.
	 * @return {boolean} True, wenn es nicht erneut gezeigt werden soll.
	 */
	function alreadySeen( cfg ) {
		if ( isPreview || 'always' === cfg.frequency ) {
			return false;
		}

		try {
			if ( 'session' === cfg.frequency ) {
				return '1' === window.sessionStorage.getItem( storageKey( cfg.id ) );
			}

			if ( 'days' === cfg.frequency ) {
				var until = parseInt( window.localStorage.getItem( storageKey( cfg.id ) ), 10 );

				return !! until && Date.now() < until;
			}
		} catch ( e ) {
			// Privater Modus ohne Speicherzugriff: lieber anzeigen.
			return false;
		}

		return false;
	}

	/**
	 * Anzeige im Browser vermerken.
	 *
	 * @param {Object} cfg Popup-Konfiguration.
	 * @return {void}
	 */
	function markSeen( cfg ) {
		if ( isPreview || 'always' === cfg.frequency ) {
			return;
		}

		try {
			if ( 'session' === cfg.frequency ) {
				window.sessionStorage.setItem( storageKey( cfg.id ), '1' );
			} else if ( 'days' === cfg.frequency ) {
				var days = cfg.frequencyDays > 0 ? cfg.frequencyDays : 1;

				window.localStorage.setItem(
					storageKey( cfg.id ),
					String( Date.now() + days * 86400000 )
				);
			}
		} catch ( e ) {
			// Kein Speicherzugriff: das Popup erscheint beim nächsten Mal wieder.
		}
	}

	/**
	 * Lässt sich das Popup manuell schliessen?
	 *
	 * @param {Object} cfg Popup-Konfiguration.
	 * @return {boolean} True, wenn Button oder Hintergrundklick aktiv sind.
	 */
	function isDismissible( cfg ) {
		return !! ( cfg.closeButton || cfg.closeOverlay );
	}

	/**
	 * Popup öffnen oder einreihen, falls bereits eines offen ist.
	 *
	 * @param {Object} item Eintrag mit Element und Konfiguration.
	 * @return {void}
	 */
	function open( item ) {
		if ( current ) {
			if ( queue.indexOf( item ) === -1 ) {
				queue.push( item );
			}

			return;
		}

		current = item;
		lastFocus = document.activeElement;

		item.el.hidden = false;
		item.el.classList.add( 'is-open' );
		document.body.classList.add( 'pm-popup-open' );

		markSeen( item.cfg );

		var box = item.el.querySelector( '.pm-popup__box' );
		var target = item.el.querySelector( '.pm-popup__close' ) || box;

		if ( target ) {
			if ( target === box ) {
				box.setAttribute( 'tabindex', '-1' );
			}

			target.focus();
		}

		if ( item.cfg.autoClose > 0 ) {
			item.autoTimer = window.setTimeout( function () {
				close( item );
			}, item.cfg.autoClose * 1000 );
		}
	}

	/**
	 * Popup schliessen und das nächste aus der Warteschlange öffnen.
	 *
	 * @param {Object} item Eintrag mit Element und Konfiguration.
	 * @return {void}
	 */
	function close( item ) {
		if ( current !== item ) {
			return;
		}

		window.clearTimeout( item.autoTimer );

		item.el.classList.remove( 'is-open' );
		item.el.hidden = true;
		document.body.classList.remove( 'pm-popup-open' );

		current = null;

		if ( lastFocus && typeof lastFocus.focus === 'function' ) {
			lastFocus.focus();
		}

		lastFocus = null;

		if ( queue.length ) {
			open( queue.shift() );
		}
	}

	/**
	 * Tab-Fokus innerhalb des offenen Popups halten.
	 *
	 * @param {KeyboardEvent} event Tastaturereignis.
	 * @return {void}
	 */
	function trapFocus( event ) {
		var box = current.el.querySelector( '.pm-popup__box' );
		var items = box ? box.querySelectorAll( FOCUSABLE ) : [];

		if ( ! items.length ) {
			event.preventDefault();

			if ( box ) {
				box.focus();
			}

			return;
		}

		var first = items[ 0 ];
		var last = items[ items.length - 1 ];

		if ( event.shiftKey && document.activeElement === first ) {
			event.preventDefault();
			last.focus();
		} else if ( ! event.shiftKey && document.activeElement === last ) {
			event.preventDefault();
			first.focus();
		}
	}

	/**
	 * Ein Popup verdrahten.
	 *
	 * @param {Object} cfg Popup-Konfiguration.
	 * @return {void}
	 */
	function setup( cfg ) {
		var el = document.getElementById( 'pm-popup-' + cfg.id );

		if ( ! el || alreadySeen( cfg ) ) {
			return;
		}

		var item = { el: el, cfg: cfg, autoTimer: null };

		el.addEventListener( 'click', function ( event ) {
			if ( event.target.closest( '[data-pm-close]' ) ) {
				event.preventDefault();
				close( item );
				return;
			}

			if ( cfg.closeOverlay && event.target.hasAttribute( 'data-pm-overlay' ) ) {
				close( item );
			}
		} );

		window.setTimeout( function () {
			open( item );
		}, Math.max( 0, cfg.delay ) * 1000 );
	}

	document.addEventListener( 'keydown', function ( event ) {
		if ( ! current ) {
			return;
		}

		if ( 'Escape' === event.key && isDismissible( current.cfg ) ) {
			close( current );
			return;
		}

		if ( 'Tab' === event.key ) {
			trapFocus( event );
		}
	} );

	/**
	 * Startet erst, wenn das Markup im Dokument steht. Nötig, falls ein
	 * Theme oder ein Optimierungs-Plugin die Skripte vorzieht.
	 *
	 * @param {Function} fn Startfunktion.
	 * @return {void}
	 */
	function ready( fn ) {
		if ( 'loading' === document.readyState ) {
			document.addEventListener( 'DOMContentLoaded', fn );
		} else {
			fn();
		}
	}

	ready( function () {
		configs.forEach( setup );
	} );
}() );
