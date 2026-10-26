// https://gist.github.com/stevendesu/2d52f7b5e1f1184af3b667c0b5e054b8?permalink_comment_id=4535312
// A simple, open-source, HMAC-SHA256 implementation in pure JavaScript. Designed for efficient minification.
// Feel free to choose whatever license you find most permissible, but I offer no warranty for the code.
// It's 100% free to do with as you please.

// To ensure cross-browser support even without a proper SubtleCrypto
// impelmentation (or without access to the impelmentation, as is the case with
// Chrome loaded over HTTP instead of HTTPS), this library can create SHA-256
// HMAC signatures using nothing but raw JavaScript

/* eslint-disable no-magic-numbers, id-length, no-param-reassign, new-cap */

// By giving internal functions names that we can mangle, future calls to
// them are reduced to a single byte (minor space savings in minified file)
var uint8Array = Uint8Array;
var uint32Array = Uint32Array;
var pow = Math.pow;

// Will be initialized below
// Using a Uint32Array instead of a simple array makes the minified code
// a bit bigger (we lose our `unshift()` hack), but comes with huge
// performance gains
var DEFAULT_STATE = new uint32Array(8);
var ROUND_CONSTANTS = [];

// Reusable object for expanded message
// Using a Uint32Array instead of a simple array makes the minified code
// 7 bytes larger, but comes with huge performance gains
var M = new uint32Array(64);

// After minification the code to compute the default state and round
// constants is smaller than the output. More importantly, this serves as a
// good educational aide for anyone wondering where the magic numbers come
// from. No magic numbers FTW!
function getFractionalBits(n)
{
	return ((n - (n | 0)) * pow(2, 32)) | 0;
}

var n = 2, nPrime = 0;
while (nPrime < 64)
{
	// isPrime() was in-lined from its original function form to save
	// a few bytes
	var isPrime = true;
	// Math.sqrt() was replaced with pow(n, 1/2) to save a few bytes
	// var sqrtN = pow(n, 1 / 2);
	// So technically to determine if a number is prime you only need to
	// check numbers up to the square root. However this function only runs
	// once and we're only computing the first 64 primes (up to 311), so on
	// any modern CPU this whole function runs in a couple milliseconds.
	// By going to n / 2 instead of sqrt(n) we net 8 byte savings and no
	// scaling performance cost
	for (var factor = 2; factor <= n / 2; factor++)
	{
		if (n % factor === 0)
		{
			isPrime = false;
		}
	}
	if (isPrime)
	{
		if (nPrime < 8)
		{
			DEFAULT_STATE[nPrime] = getFractionalBits(pow(n, 1 / 2));
		}
		ROUND_CONSTANTS[nPrime] = getFractionalBits(pow(n, 1 / 3));

		nPrime++;
	}

	n++;
}

// For cross-platform support we need to ensure that all 32-bit words are
// in the same endianness. A UTF-8 TextEncoder will return BigEndian data,
// so upon reading or writing to our ArrayBuffer we'll only swap the bytes
// if our system is LittleEndian (which is about 99% of CPUs)
var LittleEndian = !!new uint8Array(new uint32Array([1]).buffer)[0];

function convertEndian(word)
{
	if (LittleEndian)
	{
		return (
			// byte 1 -> byte 4
			(word >>> 24) |
			// byte 2 -> byte 3
			(((word >>> 16) & 0xff) << 8) |
			// byte 3 -> byte 2
			((word & 0xff00) << 8) |
			// byte 4 -> byte 1
			(word << 24)
		);
	}
	else
	{
		return word;
	}
}

function rightRotate(word, bits)
{
	return (word >>> bits) | (word << (32 - bits));
}

function sha256(data)
{
	// Copy default state
	var STATE = DEFAULT_STATE.slice();

	// Caching this reduces occurrences of ".length" in minified JavaScript
	// 3 more byte savings! :D
	var legth = data.length;

	// Pad data
	var bitLength = legth * 8;
	var newBitLength = (512 - ((bitLength + 64) % 512) - 1) + bitLength + 65;

	// "bytes" and "words" are stored BigEndian
	var bytes = new uint8Array(newBitLength / 8);
	var words = new uint32Array(bytes.buffer);

	bytes.set(data, 0);
	// Append a 1
	bytes[legth] = 0b10000000;
	// Store length in BigEndian
	words[words.length - 1] = convertEndian(bitLength);

	// Loop iterator (avoid two instances of "var") -- saves 2 bytes
	var round;

	// Process blocks (512 bits / 64 bytes / 16 words at a time)
	for (var block = 0; block < newBitLength / 32; block += 16)
	{
		var workingState = STATE.slice();

		// Rounds
		for (round = 0; round < 64; round++)
		{
			var MRound;
			// Expand message
			if (round < 16)
			{
				// Convert to platform Endianness for later math
				MRound = convertEndian(words[block + round]);
			}
			else
			{
				var gamma0x = M[round - 15];
				var gamma1x = M[round - 2];
				MRound =
					M[round - 7] + M[round - 16] + (
						rightRotate(gamma0x, 7) ^
						rightRotate(gamma0x, 18) ^
						(gamma0x >>> 3)
					) + (
						rightRotate(gamma1x, 17) ^
						rightRotate(gamma1x, 19) ^
						(gamma1x >>> 10)
					)
				;
			}

			// M array matches platform endianness
			M[round] = MRound |= 0;

			// Computation
			var t1 =
				(
					rightRotate(workingState[4], 6) ^
					rightRotate(workingState[4], 11) ^
					rightRotate(workingState[4], 25)
				) +
				(
					(workingState[4] & workingState[5]) ^
					(~workingState[4] & workingState[6])
				) + workingState[7] + MRound + ROUND_CONSTANTS[round]
			;
			var t2 =
				(
					rightRotate(workingState[0], 2) ^
					rightRotate(workingState[0], 13) ^
					rightRotate(workingState[0], 22)
				) +
				(
					(workingState[0] & workingState[1]) ^
					(workingState[2] & (workingState[0] ^
					workingState[1]))
				)
			;

			for (var i = 7; i > 0; i--)
			{
				workingState[i] = workingState[i - 1];
			}
			workingState[0] = (t1 + t2) | 0;
			workingState[4] = (workingState[4] + t1) | 0;
		}

		// Update state
		for (round = 0; round < 8; round++)
		{
			STATE[round] = (STATE[round] + workingState[round]) | 0;
		}
	}

	// Finally the state needs to be converted to BigEndian for output
	// And we want to return a Uint8Array, not a Uint32Array
	return new uint8Array(new uint32Array(
		STATE.map(function(val) { return convertEndian(val); })
	).buffer);
}

function hmac(key, data)
{
	if (key.length > 64)
		key = sha256(key);

	if (key.length < 64)
	{
		const tmp = new Uint8Array(64);
		tmp.set(key, 0);
		key = tmp;
	}

	// Generate inner and outer keys
	var innerKey = new Uint8Array(64);
	var outerKey = new Uint8Array(64);
	for (var i = 0; i < 64; i++)
	{
		innerKey[i] = 0x36 ^ key[i];
		outerKey[i] = 0x5c ^ key[i];
	}

	// Append the innerKey
	var msg = new Uint8Array(data.length + 64);
	msg.set(innerKey, 0);
	msg.set(data, 64);

	// Has the previous message and append the outerKey
	var result = new Uint8Array(64 + 32);
	result.set(outerKey, 0);
	result.set(sha256(msg), 64);

	// Hash the previous message
	return sha256(result);
}

// Convert a string to a Uint8Array, SHA-256 it, and convert back to string
const encoder = new TextEncoder("utf-8");

function sign(inputKey, inputData)
{
	const key = typeof inputKey === "string" ? encoder.encode(inputKey) : inputKey;
	const data = typeof inputData === "string" ? encoder.encode(inputData) : inputData;
	return hmac(key, data);
}

function hash(str)
{
	return hex(sha256(encoder.encode(str)));
}

function hex(bin)
{
	return bin.reduce((acc, val) =>
		acc + ("00" + val.toString(16)).substr(-2)
	, "");
}
