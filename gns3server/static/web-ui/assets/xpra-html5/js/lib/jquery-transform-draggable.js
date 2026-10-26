/*
 * xpra client
 * Licensed under MPL 2.0
 *
 * Copyright: 2021, Vasyl Gello
 *
 * Based on https://stackoverflow.com/a/24263015
 * Copyright: 2014, gal
 * License: CC-BY-SA 3.0
 */

/* General matrix transformations */

var Matrix = function(a, b, c, d, e, f, g, h, i) {
	if ($.type(a) === 'array') {
		this.elements = [
			+a[0], +a[2], +a[4],
			+a[1], +a[3], +a[5],
			0, 0, 1
		];
	} else {
		this.elements = [
			a, b, c,
			d, e, f,
			g || 0, h || 0, i || 1
		];
	}
};

Matrix.prototype = {
	/**
	 * Multiply a 3x3 matrix by a similar matrix or a vector
	 * @param {Matrix|Vector} matrix
	 * @return {Matrix|Vector} Returns a vector if multiplying by a vector
	 */
	x: function(matrix) {
		var isVector = matrix instanceof Vector;

		var a = this.elements,
			b = matrix.elements;

		if (isVector && b.length === 3) {
			// b is actually a vector
			return new Vector(
				a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
				a[3] * b[0] + a[4] * b[1] + a[5] * b[2],
				a[6] * b[0] + a[7] * b[1] + a[8] * b[2]
			);
		} else if (b.length === a.length) {
			// b is a 3x3 matrix
			return new Matrix(
				a[0] * b[0] + a[1] * b[3] + a[2] * b[6],
				a[0] * b[1] + a[1] * b[4] + a[2] * b[7],
				a[0] * b[2] + a[1] * b[5] + a[2] * b[8],

				a[3] * b[0] + a[4] * b[3] + a[5] * b[6],
				a[3] * b[1] + a[4] * b[4] + a[5] * b[7],
				a[3] * b[2] + a[4] * b[5] + a[5] * b[8],

				a[6] * b[0] + a[7] * b[3] + a[8] * b[6],
				a[6] * b[1] + a[7] * b[4] + a[8] * b[7],
				a[6] * b[2] + a[7] * b[5] + a[8] * b[8]
			);
		}
		return false; // fail
	},
	/**
	 * Generates an inverse of the current matrix
	 * @returns {Matrix}
	 */
	inverse: function() {
		var d = 1 / this.determinant(),
			a = this.elements;
		return new Matrix(
			d * (a[8] * a[4] - a[7] * a[5]),
			d * (-(a[8] * a[1] - a[7] * a[2])),
			d * (a[5] * a[1] - a[4] * a[2]),

			d * (-(a[8] * a[3] - a[6] * a[5])),
			d * (a[8] * a[0] - a[6] * a[2]),
			d * (-(a[5] * a[0] - a[3] * a[2])),

			d * (a[7] * a[3] - a[6] * a[4]),
			d * (-(a[7] * a[0] - a[6] * a[1])),
			d * (a[4] * a[0] - a[3] * a[1])
		);
	},
	/**
	 * Calculates the determinant of the current matrix
	 * @returns {Number}
	 */
	determinant: function() {
		var a = this.elements;
		return a[0] * (a[8] * a[4] - a[7] * a[5]) - a[3] * (a[8] * a[1] - a[7] * a[2]) + a[6] * (a[5] * a[1] - a[4] * a[2]);
	}
};

var Vector = function(x, y, z) {
	this.elements = [x, y, z];
};

/**
 * Get the element at zero-indexed index i
 * @param {Number} i
 */
Vector.prototype.e = Matrix.prototype.e = function(i) {

	if (this.elements[i] != undefined) {
		return this.elements[i];
	}

	return this.elements;
};

/* Draggable transformation plugin */

$.ui.plugin.add("draggable", "transform", {
	start: function(event, ui) {

		if (!$(this).data('ui-draggable')) {
			return false;
		}

		var inst = $(this).data("ui-draggable");

		inst.matrix = new Matrix(function(matrix) {

			var rmatrix = new RegExp(
				'^matrix\\(' +
				'(\\-?[\\d\\.e]+)' + '\\,?\\s*' +
				'(\\-?[\\d\\.e]+)' + '\\,?\\s*' +
				'(\\-?[\\d\\.e]+)' + '\\,?\\s*' +
				'(\\-?[\\d\\.e]+)' + '\\,?\\s*' +
				'(\\-?[\\d\\.e]+)' + '\\,?\\s*' +
				'(\\-?[\\d\\.e]+)' + '\\)$'
			);

			var matrix = rmatrix.exec(matrix);
			if (matrix) {
				matrix.shift();
			}
			return matrix || [1, 0, 0, 1, 0, 0];

		}([$(this).parents('[style*="transform"]').css('transform')]));
	},
	drag: function(event, ui) {

		if (!$(this).data('ui-draggable')) {
			return false;
		}

		var inst = $(this).data("ui-draggable");

		var t_pos = inst.matrix.inverse().x(new Vector(ui.position.left, ui.position.top, 0));

		ui.position.left = t_pos.e(0);
		ui.position.top = t_pos.e(1);

		if (inst.options.grid) {
			ui.position.left = ui.position.left - ui.position.left % inst.options.grid[0];
			ui.position.top = ui.position.top - ui.position.top % inst.options.grid[1];
		}

		if (inst.containment) {
			if (ui.position.left < inst.containment[0]) {
				ui.position.left = inst.containment[0];
			}

			if (ui.position.left > inst.containment[2]) {
				ui.position.left = inst.containment[2];
			}

			if (ui.position.top < inst.containment[1]) {
				ui.position.top = inst.containment[1];
			}

			if (ui.position.top > inst.containment[3]) {
				ui.position.top = inst.containment[3];
			}
		}
	},
});

/* Resizable transformation plugin */

$.ui.plugin.add("resizable", "transform", {
	start: function(event, ui) {

		if (!$(this).data('ui-resizable')) {
			return false;
		}

		var inst = $(this).data("ui-resizable");

		inst.matrix = new Matrix(function(matrix) {

			var rmatrix = new RegExp(
				'^matrix\\(' +
				'(\\-?[\\d\\.e]+)' + '\\,?\\s*' +
				'(\\-?[\\d\\.e]+)' + '\\,?\\s*' +
				'(\\-?[\\d\\.e]+)' + '\\,?\\s*' +
				'(\\-?[\\d\\.e]+)' + '\\,?\\s*' +
				'(\\-?[\\d\\.e]+)' + '\\,?\\s*' +
				'(\\-?[\\d\\.e]+)' + '\\)$'
			);

			var matrix = rmatrix.exec(matrix);
			if (matrix) {
				matrix.shift();
			}
			return matrix || [1, 0, 0, 1, 0, 0];

		}([$(this).parents('[style*="transform"]').css('transform')]));
	},
	resize: function(event, ui) {

		if (!$(this).data('ui-resizable')) {
			return false;
		}

		var inst = $(this).data("ui-resizable");

		if (inst.helper && inst.helper.length > 0) {
			var t_pos = inst.matrix.inverse().x(new Vector(ui.size.width, ui.size.height, 0));
			inst.helper[0].width = t_pos.e(0);
			inst.helper[0].height = t_pos.e(1);
		}
	},
});
