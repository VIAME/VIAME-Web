from typing import Dict
import xml.etree.ElementTree as ET
from dive_utils.models import Feature, Track

# data = """<?xml version="1.0" encoding="utf-8"?>
# <video id="f9e19026f17fe919fc98f34fade5feb4#201106290610">
#    <frame id="0">
#       <object h="62" species_id="1" species_name="Amphiprion Clarkii" w="119" x="12" y="90"/>
#    </frame>
#    <frame id="1">
#       <object h="62" species_id="1" species_name="Amphiprion Clarkii" w="119" x="12" y="90"/>
#    </frame>
#    <frame id="2">
#       <object h="62" species_id="1" species_name="Amphiprion Clarkii" w="119" x="12" y="90"/>
#    </frame>
#    <frame id="3">
#       <object h="62" species_id="1" species_name="Amphiprion Clarkii" w="119" x="12" y="90"/>
#    </frame>
#    <frame id="4">
#       <object h="62" species_id="1" species_name="Amphiprion Clarkii" w="119" x="12" y="90"/>
#    </frame>
#    <frame id="5">
#       <object h="62" species_id="1" species_name="Amphiprion Clarkii" w="119" x="12" y="90"/>
#    </frame>
#    <frame id="6">
#       <object h="68" species_id="1" species_name="Amphiprion Clarkii" w="115" x="12" y="84"/>
#    </frame>
#    <frame id="7">
#       <object h="68" species_id="1" species_name="Amphiprion Clarkii" w="115" x="12" y="84"/>
#    </frame>
#    <frame id="8">
#       <object h="68" species_id="1" species_name="Amphiprion Clarkii" w="115" x="12" y="84"/>
#    </frame>
#    <frame id="9">
#       <object h="68" species_id="1" species_name="Amphiprion Clarkii" w="115" x="12" y="84"/>
#    </frame>
#    <frame id="10">
#       <object h="68" species_id="1" species_name="Amphiprion Clarkii" w="115" x="12" y="84"/>
#    </frame>
#    <frame id="11">
#       <object h="68" species_id="1" species_name="Amphiprion Clarkii" w="115" x="12" y="84"/>
#    </frame>
#    <frame id="12">
#       <object h="68" species_id="1" species_name="Amphiprion Clarkii" w="115" x="12" y="84"/>
#    </frame>
#    <frame id="13">
#       <object h="68" species_id="1" species_name="Amphiprion Clarkii" w="115" x="12" y="84"/>
#    </frame>
#    <frame id="14">
#       <object h="68" species_id="1" species_name="Amphiprion Clarkii" w="115" x="12" y="84"/>
#    </frame>
#    <frame id="15">
#       <object h="70" species_id="1" species_name="Amphiprion Clarkii" w="111" x="12" y="82"/>
#    </frame>
#    <frame id="16">
#       <object h="70" species_id="1" species_name="Amphiprion Clarkii" w="111" x="12" y="82"/>
#    </frame>
#    <frame id="17">
#       <object h="70" species_id="1" species_name="Amphiprion Clarkii" w="111" x="12" y="82"/>
#    </frame>
#    <frame id="18">
#       <object h="73" species_id="1" species_name="Amphiprion Clarkii" w="111" x="12" y="79"/>
#    </frame>
#    <frame id="19">
#       <object h="73" species_id="1" species_name="Amphiprion Clarkii" w="111" x="12" y="79"/>
#    </frame>
#    <frame id="20">
#       <object h="73" species_id="1" species_name="Amphiprion Clarkii" w="111" x="12" y="79"/>
#    </frame>
#    <frame id="21">
#       <object h="82" species_id="1" species_name="Amphiprion Clarkii" w="87" x="17" y="70"/>
#    </frame>
#    <frame id="22">
#       <object h="82" species_id="1" species_name="Amphiprion Clarkii" w="87" x="17" y="70"/>
#    </frame>
#    <frame id="23">
#       <object h="82" species_id="1" species_name="Amphiprion Clarkii" w="87" x="17" y="70"/>
#    </frame>
#    <frame id="24">
#       <object h="81" species_id="1" species_name="Amphiprion Clarkii" w="65" x="16" y="64"/>
#    </frame>
#    <frame id="25">
#       <object h="81" species_id="1" species_name="Amphiprion Clarkii" w="65" x="16" y="64"/>
#    </frame>
#    <frame id="26">
#       <object h="81" species_id="1" species_name="Amphiprion Clarkii" w="65" x="16" y="64"/>
#    </frame>
#    <frame id="27">
#       <object h="96" species_id="1" species_name="Amphiprion Clarkii" w="72" x="5" y="52"/>
#    </frame>
#    <frame id="28">
#       <object h="96" species_id="1" species_name="Amphiprion Clarkii" w="72" x="5" y="52"/>
#    </frame>
#    <frame id="29">
#       <object h="96" species_id="1" species_name="Amphiprion Clarkii" w="72" x="5" y="52"/>
#    </frame>
#    <frame id="30">
#       <object h="116" species_id="1" species_name="Amphiprion Clarkii" w="72" x="5" y="30"/>
#    </frame>
#    <frame id="31">
#       <object h="116" species_id="1" species_name="Amphiprion Clarkii" w="72" x="5" y="30"/>
#    </frame>
#    <frame id="32">
#       <object h="116" species_id="1" species_name="Amphiprion Clarkii" w="72" x="5" y="30"/>
#    </frame>
#    <frame id="33">
#       <object h="123" species_id="1" species_name="Amphiprion Clarkii" w="67" x="14" y="15"/>
#    </frame>
#    <frame id="34">
#       <object h="123" species_id="1" species_name="Amphiprion Clarkii" w="67" x="14" y="15"/>
#    </frame>
#    <frame id="35">
#       <object h="123" species_id="1" species_name="Amphiprion Clarkii" w="67" x="14" y="15"/>
#    </frame>
#    <frame id="36">
#       <object h="129" species_id="1" species_name="Amphiprion Clarkii" w="73" x="16" y="0"/>
#    </frame>
#    <frame id="37">
#       <object h="129" species_id="1" species_name="Amphiprion Clarkii" w="73" x="16" y="0"/>
#    </frame>
#    <frame id="38">
#       <object h="129" species_id="1" species_name="Amphiprion Clarkii" w="73" x="16" y="0"/>
#    </frame>
#    <frame id="39">
#       <object h="131" species_id="1" species_name="Amphiprion Clarkii" w="52" x="12" y="0"/>
#    </frame>
#    <frame id="40">
#       <object h="131" species_id="1" species_name="Amphiprion Clarkii" w="52" x="12" y="0"/>
#    </frame>
#    <frame id="41">
#       <object h="131" species_id="1" species_name="Amphiprion Clarkii" w="52" x="12" y="0"/>
#    </frame>
#    <frame id="42">
#       <object h="123" species_id="1" species_name="Amphiprion Clarkii" w="57" x="4" y="0"/>
#    </frame>
#    <frame id="43">
#       <object h="123" species_id="1" species_name="Amphiprion Clarkii" w="57" x="4" y="0"/>
#    </frame>
#    <frame id="44">
#       <object h="123" species_id="1" species_name="Amphiprion Clarkii" w="57" x="4" y="0"/>
#    </frame>
#    <frame id="45">
#       <object h="98" species_id="1" species_name="Amphiprion Clarkii" w="61" x="2" y="0"/>
#    </frame>
#    <frame id="46">
#       <object h="98" species_id="1" species_name="Amphiprion Clarkii" w="61" x="2" y="0"/>
#    </frame>
#    <frame id="47">
#       <object h="98" species_id="1" species_name="Amphiprion Clarkii" w="61" x="2" y="0"/>
#    </frame>
#    <frame id="48">
#       <object h="82" species_id="1" species_name="Amphiprion Clarkii" w="61" x="2" y="0"/>
#    </frame>
#    <frame id="49">
#       <object h="82" species_id="1" species_name="Amphiprion Clarkii" w="61" x="2" y="0"/>
#    </frame>
#    <frame id="50">
#       <object h="82" species_id="1" species_name="Amphiprion Clarkii" w="61" x="2" y="0"/>
#    </frame>
#    <frame id="75">
#       <object h="41" species_id="3" species_name="Amphiprion Clarkii" w="31" x="1" y="101"/>
#    </frame>
#    <frame id="76">
#       <object h="41" species_id="3" species_name="Amphiprion Clarkii" w="31" x="1" y="101"/>
#    </frame>
#    <frame id="77">
#       <object h="41" species_id="3" species_name="Amphiprion Clarkii" w="31" x="1" y="101"/>
#    </frame>
#    <frame id="78">
#       <object h="59" species_id="3" species_name="Amphiprion Clarkii" w="33" x="1" y="88"/>
#    </frame>
#    <frame id="79">
#       <object h="59" species_id="3" species_name="Amphiprion Clarkii" w="33" x="1" y="88"/>
#    </frame>
#    <frame id="80">
#       <object h="59" species_id="3" species_name="Amphiprion Clarkii" w="33" x="1" y="88"/>
#    </frame>
#    <frame id="81">
#       <object h="59" species_id="3" species_name="Amphiprion Clarkii" w="33" x="1" y="88"/>
#    </frame>
#    <frame id="82">
#       <object h="59" species_id="3" species_name="Amphiprion Clarkii" w="33" x="1" y="88"/>
#    </frame>
#    <frame id="83">
#       <object h="59" species_id="3" species_name="Amphiprion Clarkii" w="33" x="1" y="88"/>
#    </frame>
#    <frame id="84">
#       <object h="55" species_id="3" species_name="Amphiprion Clarkii" w="33" x="1" y="92"/>
#    </frame>
#    <frame id="85">
#       <object h="55" species_id="3" species_name="Amphiprion Clarkii" w="33" x="1" y="92"/>
#    </frame>
#    <frame id="86">
#       <object h="55" species_id="3" species_name="Amphiprion Clarkii" w="33" x="1" y="92"/>
#    </frame>
#    <frame id="87">
#       <object h="55" species_id="3" species_name="Amphiprion Clarkii" w="33" x="1" y="92"/>
#    </frame>
#    <frame id="88">
#       <object h="55" species_id="3" species_name="Amphiprion Clarkii" w="33" x="1" y="92"/>
#    </frame>
#    <frame id="89">
#       <object h="55" species_id="3" species_name="Amphiprion Clarkii" w="33" x="1" y="92"/>
#    </frame>
#    <frame id="90">
#       <object h="41" species_id="3" species_name="Amphiprion Clarkii" w="53" x="1" y="106"/>
#    </frame>
#    <frame id="91">
#       <object h="41" species_id="3" species_name="Amphiprion Clarkii" w="53" x="1" y="106"/>
#    </frame>
#    <frame id="92">
#       <object h="41" species_id="3" species_name="Amphiprion Clarkii" w="53" x="1" y="106"/>
#    </frame>
#    <frame id="93">
#       <object h="39" species_id="3" species_name="Amphiprion Clarkii" w="53" x="1" y="108"/>
#    </frame>
#    <frame id="94">
#       <object h="39" species_id="3" species_name="Amphiprion Clarkii" w="53" x="1" y="108"/>
#    </frame>
#    <frame id="95">
#       <object h="39" species_id="3" species_name="Amphiprion Clarkii" w="53" x="1" y="108"/>
#    </frame>
#    <frame id="96">
#       <object h="42" species_id="3" species_name="Amphiprion Clarkii" w="64" x="1" y="108"/>
#    </frame>
#    <frame id="97">
#       <object h="44" species_id="3" species_name="Amphiprion Clarkii" w="67" x="1" y="108"/>
#    </frame>
#    <frame id="98">
#       <object h="44" species_id="3" species_name="Amphiprion Clarkii" w="67" x="1" y="108"/>
#    </frame>
#    <frame id="99">
#       <object h="44" species_id="3" species_name="Amphiprion Clarkii" w="67" x="1" y="108"/>
#    </frame>
#    <frame id="100">
#       <object h="44" species_id="3" species_name="Amphiprion Clarkii" w="67" x="1" y="108"/>
#    </frame>
#    <frame id="101">
#       <object h="48" species_id="3" species_name="Amphiprion Clarkii" w="69" x="1" y="105"/>
#    </frame>
#    <frame id="102">
#       <object h="50" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="103">
#       <object h="50" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="104">
#       <object h="50" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="105">
#       <object h="50" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="106">
#       <object h="50" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="107">
#       <object h="50" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="108">
#       <object h="50" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="109">
#       <object h="50" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="110">
#       <object h="50" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="111">
#       <object h="50" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="112">
#       <object h="50" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="113">
#       <object h="50" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="114">
#       <object h="50" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="115">
#       <object h="50" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="116">
#       <object h="50" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="117">
#       <object h="45" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="118">
#       <object h="45" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="119">
#       <object h="45" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="120">
#       <object h="45" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="121">
#       <object h="45" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="122">
#       <object h="45" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="123">
#       <object h="45" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="124">
#       <object h="45" species_id="3" species_name="Amphiprion Clarkii" w="87" x="1" y="105"/>
#    </frame>
#    <frame id="125">
#       <object h="45" species_id="3" species_name="Amphiprion Clarkii" w="81" x="1" y="105"/>
#    </frame>
#    <frame id="171">
#       <object h="25" species_id="3" species_name="Amphiprion Clarkii" w="34" x="3" y="122"/>
#    </frame>
#    <frame id="172">
#       <object h="25" species_id="3" species_name="Amphiprion Clarkii" w="34" x="3" y="122"/>
#    </frame>
#    <frame id="173">
#       <object h="25" species_id="3" species_name="Amphiprion Clarkii" w="34" x="3" y="122"/>
#    </frame>
#    <frame id="174">
#       <object h="30" species_id="3" species_name="Amphiprion Clarkii" w="34" x="3" y="117"/>
#    </frame>
#    <frame id="175">
#       <object h="30" species_id="3" species_name="Amphiprion Clarkii" w="34" x="3" y="117"/>
#    </frame>
#    <frame id="176">
#       <object h="30" species_id="3" species_name="Amphiprion Clarkii" w="34" x="3" y="117"/>
#    </frame>
#    <frame id="177">
#       <object h="35" species_id="1" species_name="Amphiprion Clarkii" w="28" x="4" y="108"/>
#    </frame>
#    <frame id="178">
#       <object h="35" species_id="1" species_name="Amphiprion Clarkii" w="28" x="4" y="108"/>
#    </frame>
#    <frame id="179">
#       <object h="35" species_id="1" species_name="Amphiprion Clarkii" w="28" x="4" y="108"/>
#    </frame>
#    <frame id="180">
#       <object h="43" species_id="1" species_name="Amphiprion Clarkii" w="31" x="2" y="104"/>
#    </frame>
#    <frame id="181">
#       <object h="43" species_id="1" species_name="Amphiprion Clarkii" w="31" x="2" y="104"/>
#    </frame>
#    <frame id="182">
#       <object h="43" species_id="1" species_name="Amphiprion Clarkii" w="31" x="2" y="104"/>
#    </frame>
#    <frame id="183">
#       <object h="48" species_id="1" species_name="Amphiprion Clarkii" w="31" x="2" y="99"/>
#    </frame>
#    <frame id="184">
#       <object h="48" species_id="1" species_name="Amphiprion Clarkii" w="31" x="2" y="99"/>
#    </frame>
#    <frame id="185">
#       <object h="48" species_id="1" species_name="Amphiprion Clarkii" w="31" x="2" y="99"/>
#    </frame>
#    <frame id="186">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="46" x="2" y="95"/>
#    </frame>
#    <frame id="187">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="46" x="2" y="95"/>
#    </frame>
#    <frame id="188">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="46" x="2" y="95"/>
#    </frame>
#    <frame id="189">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="51" x="2" y="95"/>
#    </frame>
#    <frame id="190">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="51" x="2" y="95"/>
#    </frame>
#    <frame id="191">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="51" x="2" y="95"/>
#    </frame>
#    <frame id="192">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="60" x="2" y="95"/>
#    </frame>
#    <frame id="193">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="60" x="2" y="95"/>
#    </frame>
#    <frame id="194">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="60" x="2" y="95"/>
#    </frame>
#    <frame id="195">
#       <object h="49" species_id="1" species_name="Amphiprion Clarkii" w="60" x="2" y="98"/>
#    </frame>
#    <frame id="196">
#       <object h="49" species_id="1" species_name="Amphiprion Clarkii" w="60" x="2" y="98"/>
#    </frame>
#    <frame id="197">
#       <object h="49" species_id="1" species_name="Amphiprion Clarkii" w="60" x="2" y="98"/>
#    </frame>
#    <frame id="198">
#       <object h="49" species_id="1" species_name="Amphiprion Clarkii" w="63" x="3" y="101"/>
#    </frame>
#    <frame id="199">
#       <object h="49" species_id="1" species_name="Amphiprion Clarkii" w="72" x="3" y="101"/>
#    </frame>
#    <frame id="200">
#       <object h="49" species_id="1" species_name="Amphiprion Clarkii" w="72" x="3" y="101"/>
#    </frame>
#    <frame id="201">
#       <object h="49" species_id="1" species_name="Amphiprion Clarkii" w="72" x="3" y="101"/>
#    </frame>
#    <frame id="202">
#       <object h="49" species_id="1" species_name="Amphiprion Clarkii" w="73" x="3" y="101"/>
#    </frame>
#    <frame id="203">
#       <object h="49" species_id="1" species_name="Amphiprion Clarkii" w="73" x="3" y="101"/>
#    </frame>
#    <frame id="204">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="84" x="3" y="101"/>
#    </frame>
#    <frame id="205">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="84" x="3" y="101"/>
#    </frame>
#    <frame id="206">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="84" x="3" y="101"/>
#    </frame>
#    <frame id="207">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="93" x="3" y="101"/>
#    </frame>
#    <frame id="208">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="93" x="3" y="101"/>
#    </frame>
#    <frame id="209">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="93" x="3" y="101"/>
#    </frame>
#    <frame id="210">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="89" x="3" y="101"/>
#    </frame>
#    <frame id="211">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="89" x="3" y="101"/>
#    </frame>
#    <frame id="212">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="89" x="3" y="101"/>
#    </frame>
#    <frame id="213">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="89" x="3" y="101"/>
#    </frame>
#    <frame id="214">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="89" x="3" y="101"/>
#    </frame>
#    <frame id="215">
#       <object h="52" species_id="1" species_name="Amphiprion Clarkii" w="89" x="3" y="101"/>
#    </frame>
#    <frame id="216">
#       <object h="45" species_id="1" species_name="Amphiprion Clarkii" w="82" x="3" y="106"/>
#    </frame>
#    <frame id="217">
#       <object h="45" species_id="1" species_name="Amphiprion Clarkii" w="82" x="3" y="106"/>
#    </frame>
#    <frame id="218">
#       <object h="45" species_id="1" species_name="Amphiprion Clarkii" w="82" x="3" y="106"/>
#    </frame>
#    <frame id="219">
#       <object h="45" species_id="1" species_name="Amphiprion Clarkii" w="82" x="3" y="106"/>
#    </frame>
#    <frame id="220">
#       <object h="40" species_id="1" species_name="Amphiprion Clarkii" w="78" x="3" y="106"/>
#    </frame>
#    <frame id="221">
#       <object h="40" species_id="1" species_name="Amphiprion Clarkii" w="78" x="3" y="106"/>
#    </frame>
# </video>
# """


def load_fishclef_xml_as_tracks(data: str) -> Dict[str, Track]:
    root = ET.fromstring(data)
    tracks = {}
    trackId = 0
    for frame in root.findall('frame'):
        frame_num = int(frame.get('id'))
        for obj in frame.findall('object'):
            species_id = obj.get('species_id')
            cls = obj.get('fish_species')
            x = int(obj.get('x'))
            y = int(obj.get('y'))
            w = int(obj.get('w'))
            h = int(obj.get('h'))
            feature = Feature(frame=frame_num, bounds=[x, y, x + w, y + h])
            tracks[trackId] = Track(
                frame=frame_num,
                begin=frame_num,
                end=frame_num,
                trackId=trackId,
                features=[feature],
                confidencePairs=[(cls, 1.0)],
                attributes={'species_id': species_id},
            )
            trackId += 1
    return {trackId: track.dict(exclude_none=True) for trackId, track in tracks.items()}
