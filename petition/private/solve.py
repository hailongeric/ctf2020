#!/usr/bin/env python3

from pwn import *
from Crypto.Util.number import long_to_bytes, bytes_to_long
from hashlib import sha1
from gmpy2 import invert

#
# Let's review DSA signature verification:
#
# p, q, g = group params - p and q are primes, g has order q (mod p)
# y = public key
# r, s = signature
# h = hash(message)
#
# To verify:
# a = h * s^-1 (mod q)
# b = r * s^-1 (mod q)
# v = g^a * y^b (mod p) (mod q)
# v == r # if the signature is valid
#
#
# Now, DSA verification in OpenJDK does not validate that r != 0
# https://github.com/openjdk/jdk/blob/2ae27da3bcfcdf997c93744d3dcdd30a5feb7c4f/src/java.base/share/classes/sun/security/provider/DSA.java#L353
#
# This lets an attacker forge a signature that will be valid for any key (from OpenJDK's point of view)
# The attacker must first find an exponent e such that:
#
# g^e == 0 (mod p) (mod q)
#
# Finding this exponent seems to require solving discrete log for an element that is == 0 (mod q)
# For our parameters, g^e == q (mod p) should work, since q is in the group generated by g.
#
# A forged signature would then consist of:
# r = 0
# s = e * h^-1
#
# The verification steps now become:
# a = h * (e*h^-1) = e (mod q)
# b = r * s^-1 = 0 (mod q)
# v = g^e * 1 = 0 (mod p) (mod q)
# v == r = 0  # the signature will always be valid, regardless of the public key y
#

def start():
    return remote(host='okboomer.tasteless.eu', port=10801)

    if args.HOST:
        return remote(host=args.HOST, port=int(args.PORT))

    # compile first:
    # $ javac Challenge.java
    return process(['java', 'Challenge'])


# DER encodes a sequence with two integers
def der_encode(r, s):
    r = long_to_bytes(r)
    s = long_to_bytes(s)
    size = 2 + len(r) + 2 + len(s)

    return b''.join([
        bytes([0x30, size]),
        bytes([0x02, len(r)]), r,
        bytes([0x02, len(s)]), s,
    ])


def compute_s(msg, dlog, q):
    h = bytes_to_long(sha1(msg).digest())
    return int(h * invert(dlog, q) % q)


#
# The group parameters were made small enough so that discrete log computation is feasible.
#
# The reason why q is at least 160 bits is just to stop the SHA-1 hash from being truncated,
# which could cause unnecessary confusion for solvers.
#
# sage: p = 0x1732afa753c06fd916345a525ede89ba9d78a0a8b
# sage: q = 0xb9957d3a9e037ec8b1a2d292f6f44dd4ebc50545
# sage: g = 4
# sage: %time GF(p)(q).log(g)
# ...
# Wall time: 31min 9s
# 529748506309573148992646355386290357785445171874
#

p = 0x1732afa753c06fd916345a525ede89ba9d78a0a8b
q = 0xb9957d3a9e037ec8b1a2d292f6f44dd4ebc50545
g = 4
dlog = 0x5ccabe9d4f01bf6458d169497b7a26ea75e282a2
assert pow(g, dlog, p) == q

r = 0
s = compute_s(b'We want to see the flag!', dlog, q)
petition = b64e(der_encode(r, s))

io = start()
io.sendlineafter('petition:\n', petition)
io.interactive()

#
# TODO:
# Given parameters p, q and g, is it possible to determine whether the exponent e even *exists* for certain group parameters?
#
# With the parameters in this challenge, it is easy to check all elements that are == 0 (mod p) (mod q) via
# exhaustive search: they are exactly q and 2*q, and only q is in the group generated by g (i.e. with order q).
#
# But real world DSA groups will typically use 160 bits for q, and 1024 or more for p.
# In this case, there are simply too many multiples of q to perform an exhaustive search.
# Can we check this efficiently somehow?
#
# In particular, it would be interesting to see whether g^e exists for any of the default groups that are shipped with OpenJDK:
# see https://github.com/openjdk/jdk/blob/3789983e89c9de252ef546a1b98a732a7d066650/src/java.base/share/classes/sun/security/provider/ParameterCache.java#L168
#
#
# 512-bit p, 160-bit q
# p = 0xfca682ce8e12caba26efccf7110e526db078b05edecbcd1eb4a208f3ae1617ae01f35b91a47e6df63413c5e12ed0899bcd132acd50d99151bdc43ee737592e17
# q = 0x962eddcc369cba8ebb260ee6b6a126d9346e38c5
# g = 0x678471b27a9cf44ee91a49c5147db1a9aaf244f05a434d6486931d2d14271b9e35030b71fd73da179069b32e2935630e1c2062354d0da20a6c416e50be794ca4
#
#
# 768-bit p, 160-bit q
# p = 0xe9e642599d355f37c97ffd3567120b8e25c9cd43e927b3a9670fbec5d890141922d2c3b3ad2480093799869d1e846aab49fab0ad26d2ce6a22219d470bce7d777d4a21fbe9c270b57f607002f3cef8393694cf45ee3688c11a8c56ab127a3daf
# q = 0x9cdbd84c9f1ac2f38d0f80f42ab952e7338bf511
# g = 0x30470ad5a005fb14ce2d9dcd87e38bc7d1b1c5facbaecbe95f190aa7a31d23c4dbbcbe06174544401a5b2c020965d8c2bd2171d3668445771f74ba084d2029d83c1c158547f3a9f1a2715be23d51ae4d3e5a1f6a7064f316933a346d3f529252
#
#
# 1024-bit p, 160-bit q
# p = 0xfd7f53811d75122952df4a9c2eece4e7f611b7523cef4400c31e3f80b6512669455d402251fb593d8d58fabfc5f5ba30f6cb9b556cd7813b801d346ff26660b76b9950a5a49f9fe8047b1022c24fbba9d7feb7c61bf83b57e7c6a8a6150f04fb83f6d3c51ec3023554135a169132f675f3ae2b61d72aeff22203199dd14801c7
# q = 0x9760508f15230bccb292b982a2eb840bf0581cf5
# g = 0xf7e1a085d69b3ddecbbcab5c36b857b97994afbbfa3aea82f9574c0b3d0782675159578ebad4594fe67107108180b449167123e84c281613b7cf09328cc8a6e13c167a8b547c8d28e0a3ae1e2bb3a675916ea37f0bfa213562f1fb627a01243bcca4f1bea8519089a883dfe15ae59f06928b665e807b552564014c3bfecf492a
#
#
# 2048-bit p, 224-bit q
# p = 0x8f7935d9b9aae9bfabed887acf4951b6f32ec59e3baf3718e8eac4961f3efd3606e74351a9c4183339b809e7c2ae1c539ba7475b85d011adb8b47987754984695cac0e8f14b3360828a22ffa27110a3d62a993453409a0fe696c4658f84bdd20819c3709a01057b195adcd00233dba5484b6291f9d648ef883448677979cec04b434a6ac2e75e9985de23db0292fc1118c9ffa9d8181e7338db792b730d7b9e349592f68099872153915ea3d6b8b4653c633458f803b32a4c2e0f27290256e4e3f8a3b0838a1c450e4e18c1a29a37ddf5ea143de4b66ff04903ed5cf1623e158d487c608e97f211cd81dca23cb6e380765f822e342be484c05763939601cd667
# q = 0xbaf696a68578f7dfdee7fa67c977c785ef32b233bae580c0bcd5695d
# g = 0x16a65c58204850704e7502a39757040d34da3a3478c154d4e4a5c02d242ee04f96e61e4bd0904abdac8f37eeb1e09f3182d23c9043cb642f88004160edf9ca09b32076a79c32a627f2473e91879ba2c4e744bd2081544cb55b802c368d1fa83ed489e94e0fa0688e32428a5c78c478c68d0527b71c9a3abb0b0be12c44689639e7d3ce74db101a65aa2b87f64c6826db3ec72f4b5599834bb4edb02f7c90e9a496d3a55d535bebfc45d4f619f63f3dedbb873925c2f224e07731296da887ec1e4748f87efb5fdeb75484316b2232dee553ddaf02112b0d1f02da30973224fe27aeda8b9d4b2922d9ba8be39ed9e103a63c52810bc688b7e2ed4316e1ef17dbde
#
#
# 2048-bit p, 256-bit q
# p = 0x95475cf5d93e596c3fcd1d902add02f427f5f3c7210313bb45fb4d5bb2e5fe1cbd678cd4bbdd84c9836be1f31c0777725aeb6c2fc38b85f48076fa76bcd8146cc89a6fb2f706dd719898c2083dc8d896f84062e2c9c94d137b054a8d8096adb8d51952398eeca852a0af12df83e475aa65d4ec0c38a9560d5661186ff98b9fc9eb60eee8b030376b236bc73be3acdbd74fd61c1d2475fa3077b8f080467881ff7e1ca56fee066d79506ade51edbb5443a563927dbc4ba520086746175c8885925ebc64c6147906773496990cb714ec667304e261faee33b3cbdf008e0c3fa90650d97d3909c9275bf4ac86ffcb3d03e6dfc8ada5934242dd6d3bcca2a406cb0b
# q = 0xf8183668ba5fc5bb06b5981e6d8b795d30b8978d43ca0ec572e37e09939a9773
# g = 0x42debb9da5b3d88cc956e08787ec3f3a09bba5f48b889a74aaf53174aa0fbe7e3c5b8fcd7a53bef563b0e98560328960a9517f4014d3325fc7962bf1e049370d76d1314a76137e792f3f0db859d095e4a5b932024f079ecf2ef09c797452b0770e1350782ed57ddf794979dcef23cb96f183061965c4ebc93c9c71c56b925955a75f94cccf1449ac43d586d0beee43251b0b2287349d68de0d144403f13e802f4146d882e057af19b6f6275c6676c8fa0e3ca2713a3257fd1b27d0639f695e347d8d1cf9ac819a26ca9b04cb0eb9b7b035988d15bbac65212a55239cfc7e58fae38d7250ab9991ffbc97134025fe8ce04c4399ad96569be91a546f4978693c7a
#
#
# 3072-bit p, 256-bit q
# p = 0xea9cda9f5fbda66dd830494609405687ab7cf38538e058d1e2f68dea95364866e1c05beacded24227edee28cad80bcecad39913be3b713267b3b96c8d9f0f6a03b5dfc9222d5cfe4afcc9982f33784f760c3b759aebe3bbe9098a6b84c96f1fde44ce11c084c2a082c7a76a0ef142928b4f328406ab9beb24f84577dd0f46ce86fd8f08488269998bf4742d6425f7a0ec75d8660c5dd6f4e3b3d3bee81b2c21afe8c9e8b84b87192e2cc20f961d2bcd8133afcf3675ab80681cb374c78f33e29d1011083d89f9c5728b94676fccb1b57bc60288c15d85ae838ae1941c5a20ae2b2049b3583fe30da455ddb3e6ad9b9955cd9bb5681431622beb0f92da533fcab496cebc447aa1bb5a8039522f2da98ff416289323a64df626ab6881870927dcee387f13b5c9d24d6cba1d82ed375a082506ee87bc7ae30067f4a94e2ee363d992c40f2725b5db4b3525ebde22bbbfd0fa124a588b0f5a4acb3a86951aff09f8c8198fb5b53da0c931cedc598b4f835b779d04d99026c7ba08c4b27f118ac1e3d
# q = 0xc4eeac2bbab79bd831946d717a56a6e687547aa8e9c5494a5a4b2f4ca13d6c11
# g = 0x42e5fa7844f8fa9d8998d830d004e7b15b1d276bcbe5f12c35ec90c1a25f5832018a6724bd9cdbe803b675509bed167f3d7cf8599fc865c6d5a0f79158c1bc918f00a944d0ad0f38f520fb91d85d82674d0d5f874faa5fcdfe56cd178c1afdc7ce8795727b7dee966ed0b3c5cedcef8aca628befebf2d105c7aff8eb0da9c9610737dd64dce1237b82c1b2bc8608d55ffda98d7189444e65883315669c05716bde36c78b130aa3df2e4d609914c7c8dc470f4e300187c775f81e7b1a9c0dce405d6eab2cbb9d9c4ef44412ba573dd403c4ed7bc2364772f56a30c48de78f5003f9371c55262d2c8ac2246ade3b02fdcfcf5cbfde74fbcbfe6e0e0fdf3160764f84d311c179a40af679a8f47ab13c8f706893245eb11edcce451fa2ab980019987f125d8dc96622d419ba0d71f16c6024dce9d364c3b26d8ec1a3c828f6c9d14b1d0333b95db77bfdbe3c6bce5337a1a5a7ace10111219448447197e2a344cc423be768bb89e27be6cbd22085614a5a3360be23b1bfbb6e6e6471363d32c85d31
#
